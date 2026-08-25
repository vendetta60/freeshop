"""v1 API router aggregation.

Feature routers are added here as each phase lands:
  phase 4 -> auth, users        phase 5 -> categories, products
  phase 6 -> cart, order_requests   phase 11 -> admin
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, auth, cart, categories, meta, orders, products, users

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(products.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(admin.router)
