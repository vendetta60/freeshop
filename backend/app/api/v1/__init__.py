"""v1 API router aggregation.

Feature routers are added here as each phase lands:
  phase 4 -> auth, users        phase 5 -> categories, products
  phase 6 -> cart, order_requests   phase 11 -> admin

FreeShop_Prompt phase 3 adds: needs, conversations, loans, aid,
notifications. Order matters only for paths that could shadow each other;
each router owns a distinct prefix, so it does not here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    admin_community,
    auth,
    cart,
    categories,
    emergency,
    loans,
    messages,
    meta,
    needs,
    notifications,
    orders,
    products,
    users,
)

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(products.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(needs.router)
api_router.include_router(messages.router)
api_router.include_router(loans.router)
api_router.include_router(emergency.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)
# Same `/admin` prefix, same AdminUser guard - one panel, two modules.
api_router.include_router(admin_community.router)
