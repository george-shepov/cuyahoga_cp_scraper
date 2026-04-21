#!/usr/bin/env python3
"""
CMS + Analytics Backend Service for Brockler Law
Handles content block management and serves analytics APIs
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json
import os
from pathlib import Path

# FastAPI app setup
app = FastAPI(
    title="Brockler Law - CMS & Analytics",
    description="Content management and court analytics system",
    version="1.0.0"
)

# CORS for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data storage directory
DATA_DIR = Path("/var/tmp/brockler-cms-data")
DATA_DIR.mkdir(exist_ok=True)

# Models
class ContentBlock(BaseModel):
    id: str
    title: str
    section: str
    content: str
    createdAt: str
    updatedAt: Optional[str] = None

class Product(BaseModel):
    sku: str
    name: str
    price: float
    description: str
    image: Optional[str] = None
    approved: bool = False
    popularity: int = 0  # Usage count / views
    createdAt: str
    updatedAt: Optional[str] = None

class SiteSettings(BaseModel):
    siteTitle: str
    siteDescription: str
    contactEmail: str
    phoneNumber: str

# Content Block Endpoints
@app.post("/api/blocks")
async def save_block(block: ContentBlock):
    """Save or update a content block"""
    try:
        block_file = DATA_DIR / f"block_{block.id}.json"
        block.updatedAt = datetime.now().isoformat()
        with open(block_file, 'w') as f:
            json.dump(block.dict(), f, indent=2)
        return {"status": "success", "message": f"Block '{block.id}' saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/blocks")
async def get_blocks():
    """Get all content blocks"""
    try:
        blocks = []
        for file in DATA_DIR.glob("block_*.json"):
            with open(file) as f:
                blocks.append(json.load(f))
        return blocks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/blocks/{block_id}")
async def get_block(block_id: str):
    """Get a specific content block"""
    try:
        block_file = DATA_DIR / f"block_{block_id}.json"
        if not block_file.exists():
            raise HTTPException(status_code=404, detail="Block not found")
        with open(block_file) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/blocks/{block_id}")
async def delete_block(block_id: str):
    """Delete a content block"""
    try:
        block_file = DATA_DIR / f"block_{block_id}.json"
        if block_file.exists():
            block_file.unlink()
            return {"status": "success", "message": f"Block '{block_id}' deleted"}
        raise HTTPException(status_code=404, detail="Block not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Product Endpoints
@app.post("/api/products")
async def save_product(product: Product):
    """Save or update a product"""
    try:
        product_file = DATA_DIR / f"product_{product.sku}.json"
        with open(product_file, 'w') as f:
            json.dump(product.dict(), f, indent=2)
        return {"status": "success", "message": f"Product '{product.sku}' saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
async def get_products():
    """Get all products - approved first, then sorted by popularity"""
    try:
        products = []
        for file in DATA_DIR.glob("product_*.json"):
            with open(file) as f:
                products.append(json.load(f))
        
        # Sort: Approved items first, then by popularity (descending)
        products.sort(key=lambda p: (-int(p.get('approved', False)), -p.get('popularity', 0)))
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/products/{sku}")
async def delete_product(sku: str):
    """Delete a product"""
    try:
        product_file = DATA_DIR / f"product_{sku}.json"
        if product_file.exists():
            product_file.unlink()
            return {"status": "success", "message": f"Product '{sku}' deleted"}
        raise HTTPException(status_code=404, detail="Product not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Settings Endpoints
    """Increment popularity counter when product is viewed"""
    try:
        product_file = DATA_DIR / f"product_{sku}.json"
        if not product_file.exists():
            raise HTTPException(status_code=404, detail="Product not found")
        
        with open(product_file) as f:
            product = json.load(f)
        
        product['popularity'] = product.get('popularity', 0) + 1
        
        with open(product_file, 'w') as f:
            json.dump(product, f, indent=2)
        
        return {"status": "success", "popularity": product['popularity']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/products/{sku}/approve")
async def approve_product(sku: str, approved: bool = True):
    """Approve or reject a product"""
    try:
        product_file = DATA_DIR / f"product_{sku}.json"
        if not product_file.exists():
            raise HTTPException(status_code=404, detail="Product not found")
        
        with open(product_file) as f:
            product = json.load(f)
        
        product['approved'] = approved
        product['updatedAt'] = datetime.now().isoformat()
        
        with open(product_file, 'w') as f:
            json.dump(product, f, indent=2)
        
        return {"status": "success", "approved": approved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings")
async def save_settings(settings: SiteSettings):
    """Save site settings"""
    try:
        settings_file = DATA_DIR / "site_settings.json"
        with open(settings_file, 'w') as f:
            json.dump(settings.dict(), f, indent=2)
        return {"status": "success", "message": "Settings saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    """Get site settings"""
    try:
        settings_file = DATA_DIR / "site_settings.json"
        if settings_file.exists():
            with open(settings_file) as f:
                return json.load(f)
        return {
            "siteTitle": "Brockler Law",
            "siteDescription": "Criminal defense attorney",
            "contactEmail": "contact@brocklerlaw.com",
            "phoneNumber": ""
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "brockler-cms"}

@app.get("/docs")
async def docs_redirect():
    """Redirect to Swagger docs"""
    return {"message": "CMS & Analytics API - Visit /api/docs for Swagger UI"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
