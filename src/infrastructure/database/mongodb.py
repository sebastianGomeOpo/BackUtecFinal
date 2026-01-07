"""
MongoDB connection and database wrapper
OpenAI Conversations API manages conversation state
We only use MongoDB for metadata, quotes, orders, and products
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from ...config import settings


class MongoDB:
    """MongoDB client wrapper"""
    
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect(cls):
        """Connect to MongoDB"""
        cls.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=10000,  # 10 segundos timeout
            connectTimeoutMS=10000,
            socketTimeoutMS=10000
        )
        cls.database = cls.client[settings.mongodb_db_name]
        # Verificar conexión con timeout
        await cls.client.admin.command('ping')
        print(f"✅ Connected to MongoDB: {settings.mongodb_db_name}")
    
    @classmethod
    async def disconnect(cls):
        """Disconnect from MongoDB"""
        if cls.client:
            cls.client.close()
            print("❌ Disconnected from MongoDB")
    
    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if cls.database is None:
            raise RuntimeError("Database not initialized. Call connect() first.")
        return cls.database
