import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import deferred, relationship

from app.config.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex


class PaymentMethod(str, enum.Enum):
    manual = "manual"
    paga = "paga"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_id)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)

    # Null for accounts created via Google sign-in that have never set a
    # password. AuthService guards against attempting a password login on
    # such accounts (see AuthService.login).
    hashed_password = Column(String, nullable=True)

    # Set only for accounts created or linked via Google sign-in. Unique so
    # a Google account can never be attached to more than one Logson user.
    google_id = Column(String, unique=True, index=True, nullable=True)

    # The very first account created on the platform is promoted to admin
    # automatically. Every account after that starts as a regular user and
    # can only be promoted by an existing admin (see routers/users.py).
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Running total of what this user has actually paid for successful
    # orders. There is no wallet/top-up balance in this system -- purchases
    # are paid per-order via manual transfer or Paga.
    amount_spent_kobo = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, unique=True, nullable=False)

    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False, index=True)
    vendor = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(String, ForeignKey("categories.id"), nullable=False)
    price_kobo = Column(Integer, nullable=False)
    image_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="products")
    stock_units = relationship("StockUnit", back_populates="product")

    @property
    def stock_count(self) -> int:
        return sum(1 for su in self.stock_units if not su.is_assigned)


class StockUnit(Base):
    """One purchasable unit of a product's license key inventory.

    Populated in bulk by an admin via a single textarea (one credential per
    line). Each line becomes exactly one StockUnit row.
    """

    __tablename__ = "stock_units"

    id = Column(String, primary_key=True, default=gen_id)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    credential = Column(Text, nullable=False)
    is_assigned = Column(Boolean, default=False, nullable=False)
    assigned_to_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)

    product = relationship("Product", back_populates="stock_units")


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    amount_kobo = Column(Integer, nullable=False)

    payment_method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)

    # Paga's referenceNumber for this order's payment request -- what we
    # send in every subsequent Paga call (status check, webhook matching)
    # to identify this specific transaction.
    paga_reference = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    fulfilled_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")
    product = relationship("Product")
    # Proof-of-payment image for manual transfers, kept in its own table
    # (see OrderProof). Deleting an order takes its proof with it.
    proof = relationship(
        "OrderProof",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
    )


class OrderProof(Base):
    """Proof-of-payment image for a manual bank-transfer order, stored as
    raw bytes in the database rather than on a third-party host: it stays
    private (served only through an auth-protected endpoint), needs no extra
    credentials, and -- being a brand-new table -- is created automatically
    by Base.metadata.create_all on the next boot, with no migration.

    One row per order (order_id is unique); re-uploading replaces it. The
    image bytes are deferred so listing orders (which only needs to know a
    proof *exists*) never pulls megabytes of blobs into memory."""

    __tablename__ = "order_proofs"

    id = Column(String, primary_key=True, default=gen_id)
    order_id = Column(String, ForeignKey("orders.id"), unique=True, nullable=False)
    image = deferred(Column(LargeBinary, nullable=False))
    content_type = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="proof")


class Feedback(Base):
    """A user's opinion/suggestion submitted through the store. Persisted
    here for an admin to browse later, and also emailed out immediately
    on submission -- see FeedbackService."""

    __tablename__ = "feedback"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")