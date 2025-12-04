from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic_settings import BaseSettings
from functools import lru_cache, wraps
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    database_url: str = "sqlite:///./chicken_game.db"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

# SQLite 需要特殊設定：connect_args={"check_same_thread": False}
# 這允許多執行緒存取同一個 SQLite 連線（FastAPI 的多執行緒環境需要）
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    FastAPI dependency：提供 Database Session

    使用 yield 確保 session 在請求結束後會被關閉
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def transactional(func):
    """
    Transaction decorator：確保資料庫操作的原子性

    使用方式：
        @transactional
        def some_business_logic(db: Session, ...):
            # 所有 DB 操作都在一個 transaction 內
            room = Room(...)
            db.add(room)
            # 不需要手動 commit，decorator 會處理

    如果函式內發生異常：
        - 自動 rollback
        - 異常會被重新拋出（讓上層處理）

    注意：
        - 第一個參數必須是 db: Session
        - 不要在函式內手動 commit（decorator 會處理）
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 找出 db session（可能在 args 或 kwargs）
        db = None
        if args and isinstance(args[0], Session):
            db = args[0]
        elif 'db' in kwargs:
            db = kwargs['db']

        if db is None:
            raise ValueError(
                f"@transactional requires 'db: Session' as first argument, "
                f"but got args={args}, kwargs={kwargs}"
            )

        try:
            result = func(*args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            logger.error(f"Transaction failed in {func.__name__}: {e}", exc_info=True)
            db.rollback()
            raise

    return wrapper
