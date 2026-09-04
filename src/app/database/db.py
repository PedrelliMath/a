from app.config import settings
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import Pool
import logging

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database.database_url,
    #echo=settings.app.is_development, 
    pool_size=10,                      
    max_overflow=20,                  
    pool_pre_ping=True,               
    pool_recycle=3600,              
    connect_args={
        "connect_timeout": 10,        
        "options": "-c timezone=utc"   
    }
)


SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Erro na sessão do banco de dados: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


# Colunas adicionadas depois que a tabela já existia em produção. O projeto
# não usa migrations e `create_all` só cria tabelas novas, então elas são
# aplicadas aqui, de forma idempotente, no start da aplicação.
ADDITIVE_COLUMNS: list[str] = [
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS model_messages JSONB "
    "NOT NULL DEFAULT '[]'::jsonb",
]


def apply_additive_columns() -> None:
    """Aplica as colunas aditivas pendentes. Não remove nem altera nada."""
    with engine.begin() as connection:
        for statement in ADDITIVE_COLUMNS:
            logger.info(f"Aplicando coluna aditiva: {statement}")
            connection.execute(text(statement))
