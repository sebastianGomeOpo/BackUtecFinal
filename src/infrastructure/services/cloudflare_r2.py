"""
Cloudflare R2 Service for signed image URLs
Uses boto3 for S3-compatible API
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import httpx
from typing import Optional
from ...config import settings


class CloudflareR2Service:
    """Service for managing images in Cloudflare R2 with signed URLs"""
    
    def __init__(self):
        self.endpoint = settings.cloudflare_r2_endpoint
        self.bucket = settings.cloudflare_r2_bucket
        self.access_key = settings.cloudflare_r2_access_key_id
        self.secret_key = settings.cloudflare_r2_secret_access_key
        
        # Create S3 client for R2
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
    
    def generate_presigned_url(
        self, 
        object_key: str, 
        expires_in: int = 3600,
        method: str = "get_object"
    ) -> str:
        """
        Generate a presigned URL for accessing an object in R2
        
        Args:
            object_key: The key/path of the object in the bucket
            expires_in: URL expiration time in seconds (default 1 hour)
            method: S3 method (get_object for download, put_object for upload)
        
        Returns:
            Presigned URL string
        """
        try:
            url = self.s3_client.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket, 'Key': object_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            raise Exception(f"Error generating presigned URL: {e}")
    
    def upload_image_sync(
        self, 
        image_data: bytes, 
        object_key: str,
        content_type: str = "image/jpeg"
    ) -> dict:
        """
        Upload an image to R2 (synchronous)
        
        Args:
            image_data: Binary image data
            object_key: The key/path for the object
            content_type: MIME type of the image
        
        Returns:
            Dict with success status and URL
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=image_data,
                ContentType=content_type
            )
            
            # Generate signed URL for viewing
            view_url = self.generate_presigned_url(object_key, expires_in=86400)
            return {
                "success": True,
                "object_key": object_key,
                "signed_url": view_url
            }
        except ClientError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def upload_image(
        self, 
        image_data: bytes, 
        object_key: str,
        content_type: str = "image/jpeg"
    ) -> dict:
        """
        Upload an image to R2 (async wrapper)
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.upload_image_sync, 
            image_data, 
            object_key, 
            content_type
        )
    
    async def download_and_upload_image(
        self, 
        source_url: str, 
        object_key: str
    ) -> dict:
        """
        Download an image from a URL and upload it to R2
        
        Args:
            source_url: URL to download the image from
            object_key: The key/path for the object in R2
        
        Returns:
            Dict with success status and signed URL
        """
        try:
            async with httpx.AsyncClient() as client:
                # Download image
                response = await client.get(source_url, timeout=30.0, follow_redirects=True)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to download: {response.status_code}"
                    }
                
                # Determine content type
                content_type = response.headers.get("content-type", "image/jpeg")
                if ";" in content_type:
                    content_type = content_type.split(";")[0].strip()
                
                # Upload to R2
                return await self.upload_image(
                    image_data=response.content,
                    object_key=object_key,
                    content_type=content_type
                )
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_signed_url(self, object_key: str, expires_in: int = 3600) -> str:
        """
        Get a signed URL for an existing object
        
        Args:
            object_key: The key/path of the object
            expires_in: URL expiration time in seconds
        
        Returns:
            Presigned URL string
        """
        return self.generate_presigned_url(object_key, expires_in)
    
    def list_objects(self, prefix: str = "") -> list:
        """List objects in the bucket with optional prefix"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            return response.get('Contents', [])
        except ClientError as e:
            return []


# Global instance
_r2_service: Optional[CloudflareR2Service] = None


def get_r2_service() -> CloudflareR2Service:
    """Get or create the global R2 service instance"""
    global _r2_service
    if _r2_service is None:
        _r2_service = CloudflareR2Service()
    return _r2_service
