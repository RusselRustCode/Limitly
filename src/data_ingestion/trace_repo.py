from src.core.database import get_database
from src.core.models import TraceLog
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from typing import Optional
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
class TraceRepository:

    """
    Класс для работы с коллекцие TraceLog
    """

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.student_trace_log
        self.scheduler = AsyncIOScheduler()

    
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

    async def process_batch(self):
        ...

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

