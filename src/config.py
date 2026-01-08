"""
Configuration settings for the application
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # MongoDB
    mongodb_uri: str
    mongodb_db_name: str
    
    # Pinecone
    pinecone_api_key: str
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "products-catalog"
    
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-5-mini-2025-08-07"
    
    # Gemini (Video multimodal agent)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-exp"
    
    # Cloudflare R2 (for signed image URLs)
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    cloudflare_r2_endpoint: str = ""
    cloudflare_r2_bucket: str = ""
    cloudflare_r2_access_key_id: str = ""
    cloudflare_r2_secret_access_key: str = ""
    
    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    
    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Security
    secret_key: str = "development-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Rate Limiting
    rate_limit_per_minute: int = 60
    
    # Upstash Redis (Volatile Memory)
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
