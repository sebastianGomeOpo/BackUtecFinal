"""
Products endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

from ...infrastructure.repositories.product_repository import SQLAlchemyProductRepository
from ...infrastructure.vectorstore.chroma_store import ChromaStore
from ...infrastructure.database.sqlite_db import Database
from ...domain.entities import Product

router = APIRouter()


# Request/Response models
class CreateProductRequest(BaseModel):
    name: str
    description: str
    category: str
    price: float
    stock: int
    sku: str
    images: List[str] = []
    specifications: dict = {}


class UpdateProductRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    images: Optional[List[str]] = None
    specifications: Optional[dict] = None


@router.post("/", response_model=dict)
async def create_product(request: CreateProductRequest):
    """Create a new product"""
    session_gen = Database.get_session()
    session = await anext(session_gen)
    try:
        product_repo = SQLAlchemyProductRepository(session)

        # Create product
        product = Product(
            id=str(uuid.uuid4()),
            name=request.name,
            description=request.description,
            category=request.category,
            price=request.price,
            stock=request.stock,
            sku=request.sku,
            images=request.images,
            specifications=request.specifications
        )

        # Save to database
        await product_repo.create(product)

        # Index in ChromaDB for RAG
        await ChromaStore.upsert_product(
            product_id=product.id,
            name=product.name,
            description=product.description,
            category=product.category,
            sku=product.sku
        )

        return {
            "message": "Product created successfully",
            "product_id": product.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.get("/{product_id}")
async def get_product(product_id: str):
    """Get product by ID"""
    session_gen = Database.get_session()
    session = await anext(session_gen)
    try:
        product_repo = SQLAlchemyProductRepository(session)
        product = await product_repo.get_by_id(product_id)

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        return product
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.get("/")
async def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    limit: int = 100
):
    """Search products or list all with pagination"""
    session_gen = Database.get_session()
    session = await anext(session_gen)
    try:
        product_repo = SQLAlchemyProductRepository(session)

        if category:
            all_products = await product_repo.get_by_category(category, limit)
        elif query:
            all_products = await product_repo.search(query, limit)
        else:
            all_products = await product_repo.list_all()

        # Calculate pagination
        total_count = len(all_products)
        total_pages = (total_count + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_products = all_products[start_idx:end_idx]

        # Format for frontend
        products_list = [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "price": float(p.price),
                "stock": int(p.stock),
                "category": p.category,
                "image_url": p.images[0] if p.images else None,
                "sku": p.sku
            }
            for p in paginated_products
        ]

        return {
            "products": products_list,
            "count": len(products_list),
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.put("/{product_id}")
async def update_product(product_id: str, request: UpdateProductRequest):
    """Update product"""
    session_gen = Database.get_session()
    session = await anext(session_gen)
    try:
        product_repo = SQLAlchemyProductRepository(session)

        # Get existing product
        product = await product_repo.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Update fields
        if request.name:
            product.name = request.name
        if request.description:
            product.description = request.description
        if request.category:
            product.category = request.category
        if request.price is not None:
            product.price = request.price
        if request.stock is not None:
            product.stock = request.stock
        if request.images:
            product.images = request.images
        if request.specifications:
            product.specifications = request.specifications

        # Save to database
        await product_repo.update(product)

        # Re-index in ChromaDB
        await ChromaStore.upsert_product(
            product_id=product.id,
            name=product.name,
            description=product.description,
            category=product.category,
            sku=product.sku
        )

        return {
            "message": "Product updated successfully",
            "product_id": product.id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.delete("/{product_id}")
async def delete_product(product_id: str):
    """Delete product"""
    try:
        # Delete from ChromaDB
        await ChromaStore.delete_product(product_id)

        return {
            "message": "Product deleted successfully",
            "product_id": product_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}/stock")
async def check_stock(product_id: str):
    """Check product stock"""
    session_gen = Database.get_session()
    session = await anext(session_gen)
    try:
        product_repo = SQLAlchemyProductRepository(session)
        stock = await product_repo.check_stock(product_id)

        return {
            "product_id": product_id,
            "stock": stock,
            "available": stock > 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.get("/recommend")
async def recommend_products(product_id: Optional[str] = None, limit: int = 5):
    """Get product recommendations based on a product ID or general recommendations"""
    session_gen = Database.get_session()
    session = await anext(session_gen)
    try:
        product_repo = SQLAlchemyProductRepository(session)

        if product_id:
            # Get the product to base recommendations on
            product = await product_repo.get_by_id(product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")

            # Use ChromaDB to find similar products
            similar_results = await ChromaStore.search_products(
                query=product.description,
                top_k=limit + 1  # +1 to exclude the product itself
            )

            # Extract product IDs from search results and get full product data
            product_ids = [r["id"] for r in similar_results if r["id"] != product_id]
            similar_products = await product_repo.get_by_ids(product_ids[:limit])
            recommendations = similar_products
        else:
            # Return popular or random products
            all_products = await product_repo.list_all()
            recommendations = all_products[:limit]

        # Format for frontend
        products_list = [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "price": float(p.price),
                "stock": int(p.stock),
                "category": p.category,
                "image_url": p.images[0] if p.images else None,
                "sku": p.sku
            }
            for p in recommendations
        ]

        return {
            "products": products_list,
            "count": len(products_list)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()
