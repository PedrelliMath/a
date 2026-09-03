from app.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
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