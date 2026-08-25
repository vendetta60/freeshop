"""Model registry.

Importing every model here is what puts them on ``Base.metadata``, which is
what Alembic autogenerate diffs against. A model that is not imported here is
invisible to migrations.
"""

from app.db.models.cart import CartItem
from app.db.models.order import ORDER_STATUSES, OrderRequest, OrderRequestItem
from app.db.models.product import STOCK_STATUSES, Category, Product, ProductImage
from app.db.models.setting import DEFAULT_SETTINGS, Setting
from app.db.models.user import OTP_CHANNELS, OTP_PURPOSES, ROLES, OtpCode, RefreshToken, User

__all__ = [
    "DEFAULT_SETTINGS",
    "ORDER_STATUSES",
    "OTP_CHANNELS",
    "OTP_PURPOSES",
    "ROLES",
    "STOCK_STATUSES",
    "CartItem",
    "Category",
    "OrderRequest",
    "OrderRequestItem",
    "OtpCode",
    "Product",
    "ProductImage",
    "RefreshToken",
    "Setting",
    "User",
]
