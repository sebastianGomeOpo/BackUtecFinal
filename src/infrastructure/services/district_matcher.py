"""
District matching service using Pinecone semantic search
"""
from typing import Optional, List, Dict
from ..database.mongodb import MongoDB
from ...domain.repositories import IVectorStoreRepository
from openai import OpenAI
from ...config import settings


class DistrictMatcher:
    """Match user input to district names using Pinecone semantic similarity"""
    
    _districts_cache = None
    _openai_client = None
    
    @classmethod
    def get_openai_client(cls):
        """Get or create OpenAI client"""
        if cls._openai_client is None:
            cls._openai_client = OpenAI(api_key=settings.openai_api_key)
        return cls._openai_client
    
    @classmethod
    async def get_districts(cls) -> List[Dict]:
        """Get districts from database with caching"""
        if cls._districts_cache is None:
            db = MongoDB.get_database()
            cls._districts_cache = await db.districts.find().to_list(length=None)
        return cls._districts_cache
    
    @classmethod
    async def find_district_in_text(cls, text: str) -> Optional[str]:
        """
        Search for district mentions using simple pattern matching
        (Semantic search via Pinecone would be overkill for districts)
        
        Args:
            text: User's message
            
        Returns:
            District name if found, None otherwise
        """
        if not text:
            return None
        
        text_lower = text.lower()
        districts = await cls.get_districts()
        
        if not districts:
            return None
        
        # Try exact match first
        for district in districts:
            name = district.get('name', '')
            name_lower = name.lower()
            
            # Check for exact match
            if name_lower in text_lower:
                return name
            
            # Check without "San" prefix
            if name_lower.startswith("san "):
                name_without_san = name_lower.replace("san ", "")
                if name_without_san in text_lower:
                    return name
            
            # Check for common abbreviations
            if name_lower == "miraflores" and "mira" in text_lower:
                return name
            elif name_lower == "san isidro" and "isidro" in text_lower:
                return name
            elif name_lower == "surco" and ("surco" in text_lower or "santiago" in text_lower):
                return name
            elif name_lower == "la molina" and "molina" in text_lower:
                return name
        
        return None
