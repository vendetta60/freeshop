"""Model registry.

Importing every model here is what puts them on ``Base.metadata``, which is
what Alembic autogenerate diffs against. A model that is not imported here is
invisible to migrations.
"""

from app.db.models.cart import CartItem
from app.db.models.emergency import (
    CASE_PUBLIC_STATUSES,
    CASE_STATUSES,
    COMMITMENT_STATUSES,
    COMMITMENT_TRANSITIONS,
    ITEM_PRIORITIES,
    AidCommitment,
    EmergencyAidCase,
    EmergencyAidItem,
)
from app.db.models.lending import (
    LOAN_ACTIVE_STATUSES,
    LOAN_LISTING_STATES,
    LOAN_STATUSES,
    LOAN_TERMINAL_STATUSES,
    LOAN_TRANSITIONS,
    TRANSFER_TYPES,
    LoanRequest,
)
from app.db.models.location import COUNTRY_DEFAULT, LOCATION_PRECISIONS, LocationMixin
from app.db.models.messaging import (
    CONVERSATION_TYPES,
    Conversation,
    ConversationParticipant,
    Message,
)
from app.db.models.need import NEED_MODERATION_STATUSES, NEED_STATUSES, NeedRequest
from app.db.models.notification import NOTIFICATION_TYPES, Notification
from app.db.models.order import (
    ITEM_OUTCOMES,
    ORDER_STATUSES,
    OrderRequest,
    OrderRequestItem,
)
from app.db.models.product import STOCK_STATUSES, Category, Product, ProductImage
from app.db.models.setting import DEFAULT_SETTINGS, Setting
from app.db.models.user import OTP_CHANNELS, OTP_PURPOSES, ROLES, OtpCode, RefreshToken, User

__all__ = [
    "CASE_PUBLIC_STATUSES",
    "CASE_STATUSES",
    "COMMITMENT_STATUSES",
    "COMMITMENT_TRANSITIONS",
    "CONVERSATION_TYPES",
    "COUNTRY_DEFAULT",
    "DEFAULT_SETTINGS",
    "ITEM_OUTCOMES",
    "ITEM_PRIORITIES",
    "LOAN_ACTIVE_STATUSES",
    "LOAN_LISTING_STATES",
    "LOAN_STATUSES",
    "LOAN_TERMINAL_STATUSES",
    "LOAN_TRANSITIONS",
    "LOCATION_PRECISIONS",
    "NEED_MODERATION_STATUSES",
    "NEED_STATUSES",
    "NOTIFICATION_TYPES",
    "ORDER_STATUSES",
    "OTP_CHANNELS",
    "OTP_PURPOSES",
    "ROLES",
    "STOCK_STATUSES",
    "TRANSFER_TYPES",
    "AidCommitment",
    "CartItem",
    "Category",
    "Conversation",
    "ConversationParticipant",
    "EmergencyAidCase",
    "EmergencyAidItem",
    "LoanRequest",
    "LocationMixin",
    "Message",
    "NeedRequest",
    "Notification",
    "OrderRequest",
    "OrderRequestItem",
    "OtpCode",
    "Product",
    "ProductImage",
    "RefreshToken",
    "Setting",
    "User",
]
