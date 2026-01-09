"""
FastAPI application setup and configuration
Sales Agent with LangGraph - Supervisor Architecture
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from ..config import settings


class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to handle proxy headers for correct URL generation"""
    async def dispatch(self, request: Request, call_next):
        # Check if request came through HTTPS proxy
        forwarded_proto = request.headers.get("x-forwarded-proto")
        forwarded_host = request.headers.get("x-forwarded-host")
        
        if forwarded_proto:
            request.scope["scheme"] = forwarded_proto
        if forwarded_host:
            request.scope["server"] = (forwarded_host, 443 if forwarded_proto == "https" else 80)
        
        return await call_next(request)


from ..infrastructure.database.sqlite_db import Database
from .routes import products, health, download, receipt, agent, images, audio, tts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("🚀 Starting Sales Agent API with LangGraph...")
    print("📡 Architecture: SalesAgent + Supervisor + Human-in-the-Loop")
    print("💾 Database: SQLite (Local)")
    print("🔍 Vector Store: ChromaDB (Local)")

    # Connect to databases with error handling
    try:
        await Database.connect()
        print("✅ SQLite database connected successfully")
    except Exception as e:
        print(f"❌ SQLite connection failed: {e}")
        raise

    print("✅ API startup complete")

    yield

    # Shutdown
    print("🛑 Shutting down Sales Agent API...")
    try:
        await Database.disconnect()
        print("✅ SQLite disconnected")
    except Exception as e:
        print(f"⚠️  SQLite disconnect error: {e}")
    print("✅ All services stopped gracefully")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Sales Agent API",
        description="Agente de ventas digital con IA",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Root endpoints (defined first)
    @app.get("/")
    async def root():
        return {
            "message": "BlackCombinator Sales Agent API",
            "version": "1.0.0",
            "status": "healthy"
        }
    
    @app.get("/health")
    async def health_check_root():
        return {
            "status": "healthy",
            "service": "Sales Agent API"
        }
    
    # Include routers BEFORE middleware
    app.include_router(health.router, prefix="/api", tags=["Health"])
    app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
    app.include_router(products.router, prefix="/api/products", tags=["Products"])
    app.include_router(download.router, prefix="/api/download", tags=["Download"])
    app.include_router(receipt.router, prefix="/api", tags=["Receipt"])
    app.include_router(images.router, prefix="/api/images", tags=["Images"])
    app.include_router(audio.router, prefix="/api/audio", tags=["Audio"])
    app.include_router(tts.router, prefix="/api/tts", tags=["TTS"])
    
    # Configure CORS (after routes)
    allowed_origins = settings.cors_origins_list
    if settings.app_env == "development":
        allowed_origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )
    
    return app

# Create the app instance
app = create_app()
