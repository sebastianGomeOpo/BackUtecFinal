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


from ..infrastructure.database.mongodb import MongoDB
from ..infrastructure.vectorstore.pinecone_store import PineconeStore
from .routes import products, health, download, receipt, agent, images, audio, tts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("🚀 Starting Sales Agent API with LangGraph...")
    print("📡 Architecture: SalesAgent + Supervisor + Human-in-the-Loop")
    
    # Connect to databases with error handling
    try:
        await MongoDB.connect()
        print("✅ MongoDB Atlas connected successfully")
    except Exception as e:
        print(f"⚠️  MongoDB connection failed: {e}")
        print("⚠️  API will start anyway, but database operations will fail")
    
    try:
        await PineconeStore.initialize()
        print("✅ Pinecone (Products RAG) initialized successfully")
    except Exception as e:
        print(f"⚠️  Pinecone initialization failed: {e}")
        print("⚠️  API will start anyway, but vector operations will fail")
    
    print("✅ API startup complete")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Sales Agent API...")
    try:
        await MongoDB.disconnect()
        print("✅ MongoDB disconnected")
    except Exception as e:
        print(f"⚠️  MongoDB disconnect error: {e}")
    print("✅ All services stopped gracefully")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Sales Agent API",
        description="Agente de ventas digital con IA",
        version="1.0.0",
        lifespan=lifespan,
        root_path="/",  # For proper URL generation behind proxy
    )
    
    # Configure CORS (must be before routes)
    # Get allowed origins from environment variable
    allowed_origins = settings.cors_origins_list
    
    # In development, allow all origins
    if settings.app_env == "development":
        allowed_origins = ["*"]
    
    # Add proxy headers middleware first (order matters - last added = first executed)
    app.add_middleware(ProxyHeadersMiddleware)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )
    
    # Include routers
    app.include_router(health.router, prefix="/api", tags=["Health"])
    
    # LangGraph Agent - Main
    app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
    
    # Supporting routes
    app.include_router(products.router, prefix="/api/products", tags=["Products"])
    app.include_router(download.router, prefix="/api/download", tags=["Download"])
    app.include_router(receipt.router, prefix="/api", tags=["Receipt"])
    app.include_router(images.router, prefix="/api/images", tags=["Images"])
    app.include_router(audio.router, prefix="/api/audio", tags=["Audio"])
    app.include_router(tts.router, prefix="/api/tts", tags=["TTS"])
    
    @app.get("/")
    async def root():
        return {
            "message": "BlackCombinator Sales Agent API",
            "version": "1.0.0",
            "status": "healthy"
        }
    
    # Health check endpoint for App Runner (root path)
    @app.get("/health")
    async def health_check_root():
        return {
            "status": "healthy",
            "service": "Sales Agent API"
        }
    
    @app.get("/deprecated_root")
    async def deprecated_root():
        return {
            "message": "Sales Agent API",
            "version": "1.0.0",
            "status": "running"
        }
    
    return app

# Create the app instance
app = create_app()
