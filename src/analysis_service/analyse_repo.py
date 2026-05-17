"""
AnalyseRepository — репозиторий результатов анализа цифрового следа.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from bson import ObjectId

from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.database import get_database
from src.core.models import (
    MlAnalysisResult, AnalysisTrigger, ErrorType,
    AdaptationDirective, AdaptationStrategy,
)

logger = logging.getLogger(__name__)


class AnalyseRepository:

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.ml_analysis_results


    async def save_analysis_result(self, result: MlAnalysisResult) -> str:
        try:
            doc = result.model_dump(by_alias=True, exclude_unset=True, exclude_none=True)

            # Enum → str
            if "top_error_patterns" in doc:
                doc["top_error_patterns"] = [
                    ep.value if hasattr(ep, "value") else str(ep)
                    for ep in doc["top_error_patterns"]
                ]
            if "trigger" in doc and doc["trigger"]:
                doc["trigger"] = doc["trigger"].value if hasattr(doc["trigger"], "value") else str(doc["trigger"])

            inserted = await self.collection.insert_one(doc)
            logger.info(f"[AnalyseRepository] сохранён анализ | artifact={result.artifact_id}")
            return str(inserted.inserted_id)
        except Exception as e:
            logger.error(f"[AnalyseRepository] save_analysis_result error: {e}", exc_info=True)
            raise


    async def get_latest_analysis_for_artifact(
        self, artifact_id: str
    ) -> Optional[MlAnalysisResult]:
        try:
            doc = await self.collection.find_one(
                {"artifact_id": artifact_id},
                sort=[("analysis_date", -1)],
            )
            return self._parse(doc) if doc else None
        except Exception as e:
            logger.error(f"[AnalyseRepository] get_latest error: {e}", exc_info=True)
            return None

    async def get_analysis_history_for_artifact(
        self, artifact_id: str, limit: int = 10
    ) -> List[MlAnalysisResult]:
        try:
            cursor = self.collection.find(
                {"artifact_id": artifact_id}
            ).sort("analysis_date", -1).limit(limit)
            docs = [doc async for doc in cursor]
            return [r for doc in docs if (r := self._parse(doc)) is not None]
        except Exception as e:
            logger.error(f"[AnalyseRepository] get_history error: {e}", exc_info=True)
            return []

    async def get_analysis_by_trigger(
        self, trigger: AnalysisTrigger
    ) -> List[MlAnalysisResult]:
        try:
            cursor = self.collection.find(
                {"trigger": trigger.value}
            ).sort("analysis_date", -1)
            docs = [doc async for doc in cursor]
            return [r for doc in docs if (r := self._parse(doc)) is not None]
        except Exception as e:
            logger.error(f"[AnalyseRepository] get_by_trigger error: {e}", exc_info=True)
            return []

    async def get_artifacts_needing_regeneration(
        self, threshold: float = 0.5
    ) -> List[Dict]:
        try:
            pipeline = [
                {"$match": {"efficiency_fresh": {"$lt": threshold}}},
                {"$sort": {"efficiency_fresh": 1}},
                {
                    "$group": {
                        "_id": "$artifact_id",
                        "latest_efficiency":       {"$first": "$efficiency_score"},
                        "latest_efficiency_fresh": {"$first": "$efficiency_fresh"},
                        "latest_analysis_date":    {"$first": "$analysis_date"},
                        "top_error_patterns":      {"$first": "$top_error_patterns"},
                    }
                },
            ]
            results = await self.collection.aggregate(pipeline).to_list(length=None)
            return [
                {
                    "artifact_id":      str(doc["_id"]),
                    "efficiency_score": round(doc["latest_efficiency"], 3),
                    "efficiency_fresh": round(doc["latest_efficiency_fresh"], 3),
                    "analysis_date":    doc["latest_analysis_date"],
                    "top_error_patterns": doc.get("top_error_patterns", []),
                }
                for doc in results
            ]
        except Exception as e:
            logger.error(f"[AnalyseRepository] get_needing_regen error: {e}", exc_info=True)
            return []

    async def get_all_analysis_results(self, limit: int = 100) -> List[MlAnalysisResult]:
        try:
            cursor = self.collection.find().sort("analysis_date", -1).limit(limit)
            docs = [doc async for doc in cursor]
            return [r for doc in docs if (r := self._parse(doc)) is not None]
        except Exception as e:
            logger.error(f"[AnalyseRepository] get_all error: {e}", exc_info=True)
            return []

    async def get_analysis_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date:   Optional[datetime] = None,
    ) -> Dict:
        try:
            match: Dict = {}
            if start_date or end_date:
                match["analysis_date"] = {}
                if start_date:
                    match["analysis_date"]["$gte"] = start_date
                if end_date:
                    match["analysis_date"]["$lte"] = end_date

            pipeline = [
                {"$match": match} if match else {"$match": {}},
                {
                    "$facet": {
                        "total": [{"$count": "count"}],
                        "avg":   [{"$group": {
                            "_id": None,
                            "avg_efficiency":       {"$avg": "$efficiency_score"},
                            "avg_efficiency_fresh": {"$avg": "$efficiency_fresh"},
                            "avg_mastery":          {"$avg": "$average_mastery"},
                        }}],
                        "by_trigger": [{"$group": {"_id": "$trigger", "count": {"$sum": 1}}}],
                    }
                },
            ]

            results = await self.collection.aggregate(pipeline).to_list(length=1)
            if not results:
                return {}

            facet = results[0]
            avg   = facet["avg"][0] if facet["avg"] else {}

            return {
                "total_analyses":      facet["total"][0]["count"] if facet["total"] else 0,
                "avg_efficiency":      round(avg.get("avg_efficiency", 0), 3),
                "avg_efficiency_fresh": round(avg.get("avg_efficiency_fresh", 0), 3),
                "avg_mastery":         round(avg.get("avg_mastery", 0), 3),
                "by_trigger": {
                    doc["_id"]: doc["count"]
                    for doc in facet["by_trigger"] if doc["_id"]
                },
            }
        except Exception as e:
            logger.error(f"[AnalyseRepository] get_statistics error: {e}", exc_info=True)
            return {}

    # ==================== ПАРСИНГ ====================

    def _parse(self, doc: Dict) -> Optional[MlAnalysisResult]:
        if not doc:
            return None
        try:
            doc.setdefault("efficiency_fresh", 0.0)

            if "top_error_patterns" in doc:
                parsed_patterns = []
                for ep in doc["top_error_patterns"]:
                    try:
                        parsed_patterns.append(ErrorType(ep) if isinstance(ep, str) else ep)
                    except ValueError:
                        pass
                doc["top_error_patterns"] = parsed_patterns

            if "trigger" in doc and isinstance(doc["trigger"], str):
                try:
                    doc["trigger"] = AnalysisTrigger(doc["trigger"])
                except ValueError:
                    doc["trigger"] = None

            if "adaptation_directives" in doc:
                parsed_dirs = []
                for d in doc["adaptation_directives"]:
                    if isinstance(d, dict):
                        try:
                            if "strategy" in d and isinstance(d["strategy"], str):
                                d["strategy"] = AdaptationStrategy(d["strategy"])
                            parsed_dirs.append(AdaptationDirective(**d))
                        except Exception:
                            pass
                doc["adaptation_directives"] = parsed_dirs

            return MlAnalysisResult(**doc)
        except Exception as e:
            logger.warning(f"[AnalyseRepository] ошибка парсинга doc {doc.get('_id')}: {e}")
            return None