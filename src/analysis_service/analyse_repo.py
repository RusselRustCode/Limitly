"""
AnalyseRepository — репозиторий для результатов анализа и версионных артефактов.

Поддерживает:
- Сохранение и чтение MlAnalysisResult
- Версионность GeneratedArtifact (is_active + version)
- Поиск артефактов, нуждающихся в перегенерации (по efficiency_fresh!)
"""

from typing import List, Optional, Dict
from bson import ObjectId
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.database import get_database
from src.core.models import (
    MlAnalysisResult,
    GeneratedArtifact,
    AnalysisTrigger,
    ErrorType,
    AdaptationDirective,
    AdaptationStrategy
)

class AnalyseRepository:
    """
    Репозиторий для работы с результатами анализа и артефактами.
    
    Коллекции:
    - ml_analysis_results: Результаты анализа артефактов
    - generated_artifacts: Учебные артефакты с версионностью
    """

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.analysis_collection = self.db.ml_analysis_results
        self.artifacts_collection = self.db.generated_artifacts


    async def save_analysis_result(self, result: MlAnalysisResult) -> str:
        """Сохранение результата анализа"""
        doc = result.model_dump(
            by_alias=True,
            exclude_unset=True,
            exclude_none=True
        )

        # Конвертация Enum → str
        if "top_error_patterns" in doc:
            doc["top_error_patterns"] = [
                ep.value if hasattr(ep, "value") else str(ep)
                for ep in doc["top_error_patterns"]
            ]

        if "trigger" in doc and doc["trigger"]:
            doc["trigger"] = doc["trigger"].value if hasattr(doc["trigger"], "value") else str(doc["trigger"])

        # ObjectId → str
        for field in ["artifact_id", "topic_id", "term_id"]:
            if field in doc and isinstance(doc[field], ObjectId):
                doc[field] = str(doc[field])

        inserted = await self.analysis_collection.insert_one(doc)
        return str(inserted.inserted_id)

    async def get_latest_analysis_for_artifact(self, artifact_id: str) -> Optional[MlAnalysisResult]:
        """Последний анализ для артефакта"""
        doc = await self.analysis_collection.find_one(
            {"artifact_id": artifact_id},
            sort=[("analysis_date", -1)]
        )
        return self._parse_analysis_result(doc) if doc else None

    async def get_latest_analysis_for_topic(self, topic_id: str) -> Optional[MlAnalysisResult]:
        """Последний анализ для темы"""
        doc = await self.analysis_collection.find_one(
            {"topic_id": topic_id},
            sort=[("analysis_date", -1)]
        )
        return self._parse_analysis_result(doc) if doc else None

    async def get_analysis_by_trigger(self, trigger: AnalysisTrigger) -> List[MlAnalysisResult]:
        """Анализы по типу триггера"""
        cursor = self.analysis_collection.find(
            {"trigger": trigger.value}
        ).sort("analysis_date", -1)
        docs = await cursor.to_list(length=None)
        return [self._parse_analysis_result(d) for d in docs]

    async def get_artifacts_needing_regeneration(
        self,
        threshold: float = 0.5
    ) -> List[Dict]:
        """
        Артефакты, требующие перегенерации.
        ВАЖНО: теперь используем efficiency_fresh (защита от carry-over effect).
        """
        pipeline = [
            {"$match": {"efficiency_fresh": {"$lt": threshold}}},
            {"$sort": {"efficiency_fresh": 1}},
            {
                "$group": {
                    "_id": "$artifact_id",
                    "latest_efficiency": {"$first": "$efficiency_score"},
                    "latest_efficiency_fresh": {"$first": "$efficiency_fresh"},
                    "latest_analysis_date": {"$first": "$analysis_date"},
                    "top_error_patterns": {"$first": "$top_error_patterns"}
                }
            }
        ]

        results = await self.analysis_collection.aggregate(pipeline).to_list(length=None)

        return [
            {
                "artifact_id": str(doc["_id"]),
                "efficiency_score": round(doc["latest_efficiency"], 3),
                "efficiency_fresh": round(doc["latest_efficiency_fresh"], 3),
                "analysis_date": doc["latest_analysis_date"],
                "top_error_patterns": doc.get("top_error_patterns", [])
            }
            for doc in results
        ]

    async def get_all_analysis_results(self, limit: int = 100) -> List[MlAnalysisResult]:
        cursor = self.analysis_collection.find().sort("analysis_date", -1).limit(limit)
        docs = await cursor.to_list(length=None)
        return [self._parse_analysis_result(d) for d in docs]

    async def get_analysis_history_for_artifact(
        self, artifact_id: str, limit: int = 10
    ) -> List[MlAnalysisResult]:
        cursor = self.analysis_collection.find(
            {"artifact_id": artifact_id}
        ).sort("analysis_date", -1).limit(limit)
        docs = await cursor.to_list(length=None)
        return [self._parse_analysis_result(d) for d in docs]

    def _parse_analysis_result(self, doc: Dict) -> MlAnalysisResult:
        """Парсинг документа из MongoDB"""
        if not doc:
            return None

        # Добавляем поле по умолчанию, если его нет
        if "efficiency_fresh" not in doc:
            doc["efficiency_fresh"] = 0.0

        # Enum конвертация
        if "top_error_patterns" in doc:
            doc["top_error_patterns"] = [
                ErrorType(ep) if isinstance(ep, str) else ep
                for ep in doc["top_error_patterns"]
            ]

        if "trigger" in doc and isinstance(doc["trigger"], str):
            try:
                doc["trigger"] = AnalysisTrigger(doc["trigger"])
            except ValueError:
                pass

        # Парсинг директив
        if "adaptation_directives" in doc:
            parsed = []
            for d in doc["adaptation_directives"]:
                if isinstance(d, dict):
                    if "strategy" in d and isinstance(d["strategy"], str):
                        try:
                            d["strategy"] = AdaptationStrategy(d["strategy"])
                        except ValueError:
                            pass
                    parsed.append(AdaptationDirective(**d))
            doc["adaptation_directives"] = parsed

        return MlAnalysisResult(**doc)


    async def get_artifact_by_id(self, artifact_id: str) -> Optional[GeneratedArtifact]:
        doc = await self.artifacts_collection.find_one({"_id": ObjectId(artifact_id)})
        return GeneratedArtifact(**doc) if doc else None

    async def get_active_artifact_for_term(
        self, term_id: str, artifact_type: Optional[str] = None
    ) -> Optional[GeneratedArtifact]:
        query = {"term_id": term_id, "is_active": True}
        if artifact_type:
            query["artifact_type"] = artifact_type

        doc = await self.artifacts_collection.find_one(query, sort=[("version", -1)])
        return GeneratedArtifact(**doc) if doc else None

    async def create_artifact_version(self, artifact: GeneratedArtifact) -> str:
        doc = artifact.model_dump(by_alias=True, exclude_unset=True, exclude_none=True)

        # ObjectId → str
        for field in ["material_id", "term_id", "created_by"]:   # исправлена опечатка "materia_id"
            if field in doc and isinstance(doc.get(field), ObjectId):
                doc[field] = str(doc[field])

        result = await self.artifacts_collection.insert_one(doc)
        return str(result.inserted_id)

    async def deactivate_artifact_version(self, artifact_id: str) -> bool:
        result = await self.artifacts_collection.update_one(
            {"_id": ObjectId(artifact_id)},
            {"$set": {"is_active": False}}
        )
        return result.modified_count > 0

    async def activate_artifact_version(self, artifact_id: str, term_id: str) -> bool:
        """Деактивируем все предыдущие версии и активируем новую"""
        await self.artifacts_collection.update_many(
            {"term_id": term_id, "is_active": True},
            {"$set": {"is_active": False}}
        )

        result = await self.artifacts_collection.update_one(
            {"_id": ObjectId(artifact_id)},
            {"$set": {"is_active": True}}
        )
        return result.modified_count > 0

    def _parse_artifact(self, doc: Dict) -> GeneratedArtifact:
        return GeneratedArtifact(**doc)

    # ====================== Статистика ======================

    async def get_analysis_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        match_stage = {}
        if start_date or end_date:
            match_stage["analysis_date"] = {}
            if start_date:
                match_stage["analysis_date"]["$gte"] = start_date
            if end_date:
                match_stage["analysis_date"]["$lte"] = end_date

        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {
                "$facet": {
                    "total_analyses": [{"$count": "count"}],
                    "avg_metrics": [
                        {
                            "$group": {
                                "_id": None,
                                "avg_efficiency": {"$avg": "$efficiency_score"},
                                "avg_efficiency_fresh": {"$avg": "$efficiency_fresh"},
                                "avg_mastery": {"$avg": "$average_mastery"}
                            }
                        }
                    ],
                    "by_trigger": [
                        {"$group": {"_id": "$trigger", "count": {"$sum": 1}}}
                    ]
                }
            }
        ]

        results = await self.analysis_collection.aggregate(pipeline).to_list(length=1)
        if not results:
            return {}

        facet = results[0]
        avg = facet["avg_metrics"][0] if facet["avg_metrics"] else {}

        return {
            "total_analyses": facet["total_analyses"][0]["count"] if facet["total_analyses"] else 0,
            "avg_efficiency": round(avg.get("avg_efficiency", 0), 3),
            "avg_efficiency_fresh": round(avg.get("avg_efficiency_fresh", 0), 3),
            "avg_mastery": round(avg.get("avg_mastery", 0), 3),
            "by_trigger": {doc["_id"]: doc["count"] for doc in facet["by_trigger"] if doc["_id"]}
        }