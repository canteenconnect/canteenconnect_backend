from sqlalchemy import Index
from sqlalchemy.sql import func

from app import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_gateway = db.Column(db.String(32), nullable=False)
    gateway_transaction_id = db.Column(db.String(120), nullable=True, unique=True, index=True)
    status = db.Column(db.String(24), nullable=False, index=True)
    details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    order = db.relationship("Order", back_populates="transactions")
    user = db.relationship("User", back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_created_at", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "amount": float(self.amount) if self.amount is not None else None,
            "payment_gateway": self.payment_gateway,
            "gateway_transaction_id": self.gateway_transaction_id,
            "status": self.status,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
