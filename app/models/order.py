from sqlalchemy import Index
from sqlalchemy.sql import func

from app import db

ORDER_STATUS_PENDING_PAYMENT = "PENDING_PAYMENT"
ORDER_STATUS_PENDING = "PENDING"
ORDER_STATUS_PREPARING = "PREPARING"
ORDER_STATUS_READY = "READY"
ORDER_STATUS_COMPLETED = "COMPLETED"
ORDER_STATUS_CANCELLED = "CANCELLED"
ORDER_STATUS_FAILED = "FAILED"

ORDER_STATUSES = {
    ORDER_STATUS_PENDING_PAYMENT,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_READY,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_FAILED,
}

PAYMENT_STATUS_CREATED = "CREATED"
PAYMENT_STATUS_PAID = "PAID"
PAYMENT_STATUS_FAILED = "FAILED"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    outlet_id = db.Column(db.Integer, db.ForeignKey("outlets.id", ondelete="CASCADE"), nullable=False, index=True)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    payment_status = db.Column(db.String(24), nullable=False, index=True, server_default=PAYMENT_STATUS_CREATED)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = db.relationship("User", back_populates="orders")
    outlet = db.relationship("Outlet", back_populates="orders")
    order_items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="order")
    transactions = db.relationship("Transaction", back_populates="order")

    __table_args__ = (
        Index("ix_orders_created_at", "created_at"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_user_id", "user_id"),
        Index("ix_orders_outlet_id", "outlet_id"),
    )

    def to_dict(self, include_items: bool = False):
        payload = {
            "id": self.id,
            "order_number": self.order_number,
            "user_id": self.user_id,
            "outlet_id": self.outlet_id,
            "total_amount": float(self.total_amount) if self.total_amount is not None else None,
            "status": self.status,
            "payment_status": self.payment_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_items:
            payload["items"] = [item.to_dict() for item in self.order_items]
        return payload


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(12, 2), nullable=False)

    order = db.relationship("Order", back_populates="order_items")
    menu_item = db.relationship("MenuItem", back_populates="order_items")

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "menu_item_id": self.menu_item_id,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price) if self.unit_price is not None else None,
            "line_total": float(self.line_total) if self.line_total is not None else None,
            "menu_item": self.menu_item.to_dict() if self.menu_item else None,
        }
