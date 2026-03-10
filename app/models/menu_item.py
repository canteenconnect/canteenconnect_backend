from sqlalchemy import Index
from sqlalchemy.sql import func

from app import db


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)
    outlet_id = db.Column(
        db.Integer,
        db.ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    available_quantity = db.Column(db.Integer, nullable=False, server_default="0")
    is_available = db.Column(db.Boolean, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    outlet = db.relationship("Outlet", back_populates="menu_items")
    order_items = db.relationship("OrderItem", back_populates="menu_item")

    __table_args__ = (
        Index("ix_menu_items_outlet_id_name", "outlet_id", "name"),
        Index("ix_menu_items_is_available", "is_available"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "outlet_id": self.outlet_id,
            "name": self.name,
            "description": self.description,
            "price": float(self.price) if self.price is not None else None,
            "available_quantity": self.available_quantity,
            "is_available": self.is_available,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
