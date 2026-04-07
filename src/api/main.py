from fastapi import FastAPI, HTTPException, Depends
from config.settings import settings
from src.core.database import connect_to_mongo, close_mongo_db
from src.data_ingestion.trace_repo import TraceRepository
from src.api.routers.v1 import auth
from src.api.routers.v1.auth import router
from src.api.routers.v1.llm import llm_router
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from authx import AuthX, AuthXConfig


config = AuthXConfig(
    JWT_SECRET_KEY = "pZQaAqLu8AzwEatgwxMDifP9kj3Jjh6IJr-VQKOaS7o",
    JWT_ALGORITHM = settings.JWT_ALGORITHM,
    # JWT_ACCESS_TOKEN_EXPIRE = settings.JWT_ACCESS_TOKEN_EXPIRE,
    JWT_TOKEN_LOCATION = ["cookies"],
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],  # или ["*"] для разработки
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


auth = AuthX(config=config)
auth.handle_errors(app)


@app.on_event("startup")
async def startup_event():
    print("Hello world")
    connect_to_mongo()

    app.state.trace_repo = TraceRepository()

    app.state.log_watcher_task = asyncio.create_task(app.state.trace_repo.watch_log())
    print("Фоновая задача запущена")

@app.on_event("shutdown")
async def shutdown_event():
    print("Bye world")
    if hasattr(app.state, 'log_watcher_task') and app.state.log_watcher_task:
        app.state.log_watcher_task.cancel()
        print("Фоновая задача отменнена")

    close_mongo_db()


app.include_router(
    router,
    prefix=settings.API_V1_STR,
    tags=["Auth"]
)

from src.api.routers.v1.analysis import analyse_router
app.include_router(
    analyse_router,
    prefix=settings.API_V1_STR,
)

from src.api.routers.v1.analysis_cs import analysis_router
app.include_router(
    analysis_router,
    prefix=settings.API_V1_STR,
    tags=["Analysis Module (CS)"]
)


app.include_router(
    llm_router,
    prefix=settings.API_V1_STR,
)

