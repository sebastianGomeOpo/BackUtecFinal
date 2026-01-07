"""
Download endpoints for PDFs and files
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter()


@router.get("/pdf/{filename}")
async def download_pdf(filename: str):
    """Download a PDF file"""
    # Security: Only allow PDF files
    if not filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Sanitize filename to prevent path traversal
    filename = os.path.basename(filename)
    
    pdf_dir = os.path.join(os.getcwd(), 'pdfs')
    file_path = os.path.join(pdf_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/pdf'
    )
