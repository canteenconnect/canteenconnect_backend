from sqlalchemy import Index
from sqlalchemy.sql import func

from app import db


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(8), nullable=False, server_default="INR")
    gateway = db.Column(db.String(32), nullable=False)
    gateway_order_id = db.Column(db.String(120), nullable=True, index=True)
    gateway_payment_id = db.Column(db.String(120), nullable=True, index=True)
    gateway_signature = db.Column(db.String(255))
    status = db.Column(db.String(24), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    order = db.relationship("Order", back_populates="payments")
    user = db.relationship("User", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_gateway_order_id", "gateway_order_id"),
        Index("ix_payments_gateway_payment_id", "gateway_payment_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "amount": float(self.amount) if self.amount is not None else None,
            "currency": self.currency,
            "gateway": self.gateway,
            "gateway_order_id": self.gateway_order_id,
            "gateway_payment_id": self.gateway_payment_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
