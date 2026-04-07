from src.core.database import get_database
from src.core.models import TraceLog
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from typing import Optional
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pandas as pd

# TODO: Вернуть импорты после реализации старых анализаторов
# from src.analysis_service.cluster_student import run_clustering
# from src.analysis_service.engagement_analyse import EngagementAnalyzer
# from src.analysis_service.effeciency_material_analyse import MaterialEffectivenessAnalyzer
class TraceRepository:

    """
    Класс для работы с коллекцие TraceLog
    """

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.student_trace_log
        self.scheduler = AsyncIOScheduler()
        self.generated_collection = self.db.generated_artifacts

    
    async def run_analysis_job(self):
        print(f"[{datetime.now()}] Запуск планового анализа цифрового следа...")
        
        time_threshold = datetime.utcnow() - timedelta(hours=12)
        query = {"timestamp": {"$gte": time_threshold}}
        
        logs = await self.get_logs_by_filter(query)
        
        if logs:
            print(f"Найдено {len(logs)} логов для анализа.")
            self.process_batch()
        else:
            print("Новых логов для анализа не найдено.")

    async def process_batch(self, logs: List[TraceLog]):
        if not logs:
            return
        
        data = []
        for log in logs:
            log_dict = log.model_dump()
            data.append({
                "student_id": log_dict["student_id"],
                "material_id": log_dict["material_id"],
                "artifact_type": "test_question",
                "attempts": log_dict["attempts"],
                "correctness": log_dict["is_correct"],
                "time_spent_sec": log_dict["time_spent_on_q"], 
                "selected_distractor": log_dict["selected_distractor"],
                "timestamp": log_dict["timestamped"]
            })
        
        df = pd.DataFrame(data=data)
        try:
            # TODO: Вернуть анализ после реализации новых модулей
            # df_clustered, _, _ = run_clustering(df)
            # mat_analyzer = MaterialEffectivenessAnalyzer(df)
            # material_metrics = mat_analyzer.calculate_material_metrics()
            # eng_analyzer = EngagementAnalyzer(df)
            # eng_analyzer.calculate_active_metrics()
            # eng_analyzer.calculate_learning_patterns()
            # eng_analyzer.calculate_temp_patterns()
            # eng_analyzer.calculate_risk_scores()
            print(f"Обработано {len(logs)} логов")
        except Exception as e:
            print(f"Error: {e}")

    async def get_logs_by_filter(self, filter_query: dict, limit: Optional[int] = None, sort_by = "timestamp", sort_order = -1) -> Optional[List[TraceLog]]:
        try:
            raws = self.collection.find(filter_query)

            if sort_by:
                raws = raws.sort(sort_by, sort_order)
            if limit:
                raws = raws.limit(limit)

            raw_logs = []

            async for raw in raws:
                raw_logs.append(raw)

            if not raw_logs:
                return None

            logs = [TraceLog(**log) for log in raw_logs]
            return logs
        except Exception as e:
            print(f"Ошибка при получение логов по фильтру {filter_query}: {e}")
            return None

    async def get_logs_by_artifact(
        self, 
        artifact_id: str,
        limit: Optional[int] = None
    ) -> List[TraceLog]:
        """
        Получение логов по ID артефакта.
        
        Args:
            artifact_id: ID артефакта
            limit: Максимальное количество записей
        
        Returns:
            Список TraceLog
        """
        from bson import ObjectId
        try:
            query = {"artifact_id": ObjectId(artifact_id)}
            raws = self.collection.find(query)
            
            if limit:
                raws = raws.limit(limit)
            
            raw_logs = [raw async for raw in raws]
            
            if not raw_logs:
                return []
            
            return [TraceLog(**log) for log in raw_logs]
        except Exception as e:
            print(f"Ошибка при получение логов по artifact_id {artifact_id}: {e}")
            return []

    async def get_logs_by_student_and_artifact(
        self,
        student_id: str,
        artifact_id: str
    ) -> List[TraceLog]:
        """
        Получение логов по ID студента и артефакта.
        
        Args:
            student_id: ID студента
            artifact_id: ID артефакта
        
        Returns:
            Список TraceLog
        """
        from bson import ObjectId
        try:
            query = {
                "student_id": ObjectId(student_id),
                "artifact_id": ObjectId(artifact_id)
            }
            raws = self.collection.find(query)
            raw_logs = [raw async for raw in raws]
            
            if not raw_logs:
                return []
            
            return [TraceLog(**log) for log in raw_logs]
        except Exception as e:
            print(f"Ошибка при получение логов по student_id {student_id} и artifact_id {artifact_id}: {e}")
            return []

    async def get_log_by_student_id(self, student_id: str) -> List[TraceLog]:
        return await self.get_logs_by_filter({"student_id": student_id})

    async def get_log_by_material_id(self, material_id: str) -> List[TraceLog]:
        return await self.get_logs_by_filter({"material_id": material_id})
    
    def start_scheduled_jobs(self):
        self.scheduler.add_job(self.run_analysis_job, 'cron', hour = '0,12')
        
        
        #Для проверки
        # self.scheduler.add_job(self.run_analysis_job, 'interval')
        
        self.scheduler.start()
        print("Планировщик запущен")

