"""
SQLite Database connection and initialization
Async wrapper for aiosqlite + SQLAlchemy
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from pathlib import Path
from .models import Base, register_sqlite_pragma
from ...config import settings
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager"""

    engine: AsyncEngine = None
    async_session_maker: async_sessionmaker = None

    @classmethod
    async def connect(cls):
        """Connect to SQLite database and create tables"""
        try:
            # Ensure data directory exists
            db_path = Path(settings.database_url.replace("sqlite+aiosqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create async engine
            cls.engine = create_async_engine(
                settings.database_url,
                echo=False,  # Set to True for SQL debugging
                future=True,
                pool_pre_ping=True,
            )

            # Register SQLite pragmas for better performance
            register_sqlite_pragma(cls.engine)

            # Create session factory
            cls.async_session_maker = async_sessionmaker(
                cls.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

            # Create all tables (checkfirst=True to avoid errors if they exist)
            async with cls.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all, checkfirst=True)

            logger.info(f"✅ SQLite database initialized: {settings.database_url}")

        except Exception as e:
            logger.error(f"❌ Failed to connect to SQLite database: {e}")
            raise

    @classmethod
    async def disconnect(cls):
        """Disconnect from SQLite database"""
        if cls.engine:
            await cls.engine.dispose()
            logger.info("❌ Disconnected from SQLite database")

    @classmethod
    async def get_session(cls) -> AsyncSession:
        """Get an async session for database operations"""
        if cls.async_session_maker is None:
            raise RuntimeError("Database not initialized. Call connect() first.")

        async with cls.async_session_maker() as session:
            yield session

    @classmethod
    async def execute_query(cls, statement):
        """Execute a raw query and return results"""
        async with cls.async_session_maker() as session:
            result = await session.execute(statement)
            return result

    @classmethod
    async def init_db(cls):
        """Initialize database (called during startup)"""
        await cls.connect()

    @classmethod
    async def cleanup_db(cls):
        """Cleanup database (called during shutdown)"""
        await cls.disconnect()
