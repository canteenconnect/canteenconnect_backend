from sqlalchemy import Index
from sqlalchemy.sql import func

from app import db


class Outlet(db.Model):
    __tablename__ = "outlets"

    id = db.Column(db.Integer, primary_key=True)
    campus_id = db.Column(
        db.Integer,
        db.ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    campus = db.relationship("Campus", back_populates="outlets")
    menu_items = db.relationship("MenuItem", back_populates="outlet", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="outlet")
    vendors = db.relationship("User", back_populates="outlet")

    __table_args__ = (
        Index("ix_outlets_campus_id_name", "campus_id", "name", unique=True),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "campus_id": self.campus_id,
            "name": self.name,
            "location": self.location,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
