"""
Image endpoints - Cloudflare R2 signed URLs
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from ...infrastructure.services.cloudflare_r2 import get_r2_service

router = APIRouter()


class SignedUrlRequest(BaseModel):
    object_key: str
    expires_in: Optional[int] = 3600


class UploadFromUrlRequest(BaseModel):
    source_url: str
    object_key: str


@router.post("/signed-url")
async def get_signed_url(request: SignedUrlRequest):
    """Get a signed URL for an image in R2"""
    try:
        r2 = get_r2_service()
        signed_url = r2.get_signed_url(request.object_key, request.expires_in)
        
        return {
            "success": True,
            "object_key": request.object_key,
            "signed_url": signed_url,
            "expires_in": request.expires_in
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_image(file: UploadFile = File(...), object_key: Optional[str] = None):
    """Upload an image to R2"""
    try:
        r2 = get_r2_service()
        
        # Generate object key if not provided
        if not object_key:
            import uuid
            ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
            object_key = f"products/{uuid.uuid4()}.{ext}"
        
        # Read file content
        content = await file.read()
        
        # Upload to R2
        result = await r2.upload_image(
            image_data=content,
            object_key=object_key,
            content_type=file.content_type or "image/jpeg"
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-from-url")
async def upload_from_url(request: UploadFromUrlRequest):
    """Download an image from URL and upload to R2"""
    try:
        r2 = get_r2_service()
        result = await r2.download_and_upload_image(
            source_url=request.source_url,
            object_key=request.object_key
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/product/{product_id}")
async def get_product_image(product_id: str):
    """Get signed URL for a product image"""
    try:
        r2 = get_r2_service()
        object_key = f"products/{product_id}.jpg"
        signed_url = r2.get_signed_url(object_key, expires_in=3600)
        
        return {
            "product_id": product_id,
            "signed_url": signed_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
