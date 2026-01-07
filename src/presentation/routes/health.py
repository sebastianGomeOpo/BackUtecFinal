"""
Health check endpoints
"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
@router.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Sales Agent API"
    }


@router.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return {"message": "pong"}


@router.get("/test-db")
async def test_database():
    """Test database connections"""
    from ...infrastructure.database.mongodb import MongoDB
    
    results = {
        "mongodb": "unknown"
    }
    
    try:
        db = MongoDB.get_database()
        results["mongodb"] = "connected" if db else "disconnected"
    except Exception as e:
        results["mongodb"] = f"error: {str(e)}"
    
    return results
