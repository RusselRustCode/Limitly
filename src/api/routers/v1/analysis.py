from fastapi import APIRouter, Query, HTTPException
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import traceback
from src.analysis_service.analyse_repo import AnalyseRepository
# from src.analysis_service.cluster_student import run_clustering  
# from src.analysis_service.engagement_analyse import EngagementAnalyzer
# from src.analysis_service.effeciency_material_analyse import MaterialEffectivenessAnalyzer

# === Настройки MongoDB ===
MONGO_URI = "mongodb+srv://admin_db_user:LWMbq8tq8HcalReD@limithy.c6tgjuz.mongodb.net/limithy?appName=Limithy"
DB_NAME = "LimithyDB"
COLLECTION_NAME = "student_trace_logs"

def get_student_logs_df() -> pd.DataFrame:
    """Загружает student_trace_logs в DataFrame."""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    logs = list(collection.find({}, {"_id": 0}))
    if not logs:
        raise HTTPException(status_code=404, detail="Нет данных в student_trace_logs")
    df = pd.DataFrame(logs)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

analyse_router = APIRouter(prefix="/analyse", tags=["Analysis"])

def get_analyse_repo() -> AnalyseRepository:
    return AnalyseRepository()

