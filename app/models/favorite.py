from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.sql import func

from app import db


class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    user = db.relationship("User", back_populates="favorites")
    menu_item = db.relationship("MenuItem", back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("user_id", "menu_item_id", name="ux_favorites_user_menu_item"),
        Index("ix_favorites_created_at", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "menu_item_id": self.menu_item_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
