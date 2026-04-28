"""
FastAPI приложение — точка входа.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from authx import AuthX, AuthXConfig

from config.settings import settings
from src.core.database import connect_to_mongo, close_mongo_db
from src.core.logging_config import setup_logging
from src.core.error_handler import setup_exception_handlers

# Логирование инициализируется первым
setup_logging()

import logging
logger = logging.getLogger(__name__)

config = AuthXConfig(
    JWT_SECRET_KEY     = settings.JWT_SECRET_KEY,
    JWT_ALGORITHM      = settings.JWT_ALGORITHM,
    JWT_TOKEN_LOCATION = ["cookies"],
)

app = FastAPI(
    title       = settings.PROJECT_NAME,
    openapi_url = f"{settings.API_V1_STR}/openapi.json",
    description = "ИИ-ассистент преподавателя: генерация, анализ и адаптация учебных материалов",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

setup_exception_handlers(app)

auth = AuthX(config=config)
auth.handle_errors(app)



@app.on_event("startup")
async def startup_event():
    connect_to_mongo()
    logger.info(f"{settings.PROJECT_NAME} запущен")


@app.on_event("shutdown")
async def shutdown_event():
    close_mongo_db()
    logger.info("Соединение с БД закрыто")


# ==================== РОУТЕРЫ ====================

from src.api.routers.v1.auth         import router          as auth_router
from src.api.routers.v1.llm          import llm_router
from src.api.routers.v1.analysis_cs  import analysis_router
from src.api.routers.v1.trace        import trace_router
from src.api.routers.v1.simulator    import simulator_router
from src.api.routers.v1.regeneration import regen_router

P = settings.API_V1_STR

app.include_router(auth_router,      prefix=P, tags=["Auth"])
app.include_router(llm_router,       prefix=P)
app.include_router(analysis_router,  prefix=P)
app.include_router(trace_router,     prefix=P)
app.include_router(simulator_router, prefix=P)
app.include_router(regen_router,     prefix=P)