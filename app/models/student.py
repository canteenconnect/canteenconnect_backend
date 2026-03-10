from sqlalchemy.sql import func

from app import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    roll_number = db.Column(db.String(64), nullable=False, unique=True, index=True)
    department = db.Column(db.String(120), nullable=False)
    wallet_balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    user = db.relationship("User", back_populates="student")
    orders = db.relationship("Order", back_populates="student", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "roll_number": self.roll_number,
            "department": self.department,
            "wallet_balance": float(self.wallet_balance or 0),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

