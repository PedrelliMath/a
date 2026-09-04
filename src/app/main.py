from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError

from contextlib import asynccontextmanager
from pathlib import Path

from app.routers import skill, session, evaluation, assessment_properties

from app.config import settings
from app.database.db import engine, Base, apply_additive_columns
from app.openapi_keycloak import init_custom_open_api

from app.logger import get_log


logger = get_log(__name__)

# Diretório public relativo ao arquivo main.py
PUBLIC_DIR = Path(__file__).parent / "public"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando aplicação...")
    logger.info(f"Modo: {settings.app.app_mode}")
    logger.info(f"Host: {settings.app.app_host}:{settings.app.app_port}")
    
    try:
        logger.info("Criando tabelas no banco de dados...")
        Base.metadata.create_all(bind=engine)
        apply_additive_columns()
        logger.info("Tabelas criadas com sucesso!")
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {str(e)}")
        raise
    
    yield
    
    logger.info("Encerrando aplicação...")


app = FastAPI(
    title="Assessment API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_init_oauth={
        "clientId": "chatbot-frontend",
        "appName": "Assessment API - Swagger UI",
        "usePkceWithAuthorizationCodeGrant": True, 
        "scopes": "openid profile email",    
    }
)

app.openapi_schema = None
app.openapi = init_custom_open_api(app)

app.mount("/public", StaticFiles(directory="public", html=True), name="public")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Erro de validação: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Erro de validação",
            "errors": exc.errors()
        }
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Erro no banco de dados: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Erro interno no banco de dados",
            "message": "Ocorreu um erro ao processar sua requisição."
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Erro não tratado: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Erro interno do servidor",
            "message": "Ocorreu um erro inesperado"
        }
    )

@app.get(
    "/",
    tags=["Health"],
    summary="Health Check",
)
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "mode": settings.app.app_mode,
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/chat")
async def chat_bot_frontend():
    return FileResponse("public/index.html")

app.include_router(
    skill.router,
    prefix="/api/v1"
)

app.include_router(
    session.router,
    prefix="/api/v1"
)

app.include_router(
    evaluation.router,
    prefix="/api/v1"
)

app.include_router(
    assessment_properties.router,
    prefix="/api/v1"
)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.app.app_host,
        port=settings.app.app_port,
        reload=settings.app.is_development,
        log_level="info"
    )