"""
Main entry point for the Sales Agent API
"""
import uvicorn
from src.presentation.api import create_app

# Create app instance (needed for uvicorn reload)
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
