from sqlalchemy import Index
from sqlalchemy.sql import func

from app import bcrypt, db

ROLE_STUDENT = "STUDENT"
ROLE_VENDOR = "VENDOR"
ROLE_ADMIN = "ADMIN"
ROLE_SUPER_ADMIN = "SUPER_ADMIN"

USER_ROLES = {ROLE_STUDENT, ROLE_VENDOR, ROLE_ADMIN, ROLE_SUPER_ADMIN}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(
        db.Integer,
        db.ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    campus_id = db.Column(db.Integer, db.ForeignKey("campuses.id", ondelete="SET NULL"), index=True)
    outlet_id = db.Column(db.Integer, db.ForeignKey("outlets.id", ondelete="SET NULL"), index=True)
    roll_number = db.Column(db.String(64), unique=True, index=True)
    department = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    role = db.relationship("Role", back_populates="users")
    campus = db.relationship("Campus", back_populates="users")
    outlet = db.relationship("Outlet", back_populates="vendors")
    orders = db.relationship("Order", back_populates="user")
    payments = db.relationship("Payment", back_populates="user")
    transactions = db.relationship("Transaction", back_populates="user")
    audit_logs = db.relationship("AuditLog", back_populates="user")
    favorites = db.relationship("Favorite", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_users_role_id", "role_id"),
        Index("ix_users_campus_id", "campus_id"),
        Index("ix_users_outlet_id", "outlet_id"),
    )

    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role.name if self.role else None,
            "role_id": self.role_id,
            "campus_id": self.campus_id,
            "outlet_id": self.outlet_id,
            "roll_number": self.roll_number,
            "department": self.department,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
