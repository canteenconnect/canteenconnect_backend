from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MenuItem, Outlet, Student, User
from .security import hash_password


def seed_data(db: Session):
    if not db.execute(select(User).where(User.email == "super.admin@smartcampus.io")).scalar_one_or_none():
        db.add(
            User(
                name="Super Admin",
                email="super.admin@smartcampus.io",
                password_hash=hash_password("Secure@123"),
                role="admin",
            )
        )

    if not db.execute(select(User).where(User.email == "campus.admin@northbridge.edu")).scalar_one_or_none():
        db.add(
            User(
                name="Campus Admin",
                email="campus.admin@northbridge.edu",
                password_hash=hash_password("Secure@123"),
                role="admin",
            )
        )

    if not db.execute(select(User).where(User.email == "kitchen.staff@northbridge.edu")).scalar_one_or_none():
        db.add(
            User(
                name="Kitchen Staff",
                email="kitchen.staff@northbridge.edu",
                password_hash=hash_password("Secure@123"),
                role="kitchen",
            )
        )

    student_user = db.execute(select(User).where(User.email == "student1@northbridge.edu")).scalar_one_or_none()
    if not student_user:
        student_user = User(
            name="Student One",
            email="student1@northbridge.edu",
            password_hash=hash_password("Secure@123"),
            role="student",
        )
        db.add(student_user)
        db.flush()

    if not db.execute(select(Student).where(Student.user_id == student_user.id)).scalar_one_or_none():
        db.add(
            Student(
                user_id=student_user.id,
                roll_number="NB-2026-001",
                department="CSE",
                wallet_balance=Decimal("1000.00"),
            )
        )

    outlet = db.execute(select(Outlet).where(Outlet.name == "Main Canteen")).scalar_one_or_none()
    if not outlet:
        outlet = Outlet(name="Main Canteen", location="Block A", is_active=True)
        db.add(outlet)
        db.flush()

    menu_items = [
        ("Veg Fried Rice", "Street-style veg fried rice", Decimal("110"), 120),
        ("Egg Fried Rice", "Egg fried rice", Decimal("130"), 100),
        ("Chicken Fried Rice", "Chicken fried rice", Decimal("150"), 90),
        ("Gobi Fried Rice", "Gobi fried rice", Decimal("125"), 80),
        ("Veg Noodles", "Veg hakka noodles", Decimal("105"), 110),
        ("Egg Noodles", "Egg noodles", Decimal("125"), 100),
        ("Chicken Noodles", "Chicken noodles", Decimal("145"), 90),
        ("Gobi Noodles", "Gobi noodles", Decimal("120"), 80),
        ("Veg Puff", "Fresh veg puff", Decimal("35"), 150),
        ("Egg Puff", "Egg puff", Decimal("45"), 140),
        ("Chicken Puff", "Chicken puff", Decimal("55"), 120),
        ("Cola (300ml)", "Chilled cola", Decimal("40"), 200),
        ("Lemon Soda", "Lemon soda", Decimal("35"), 180),
        ("Orange Fizz", "Orange drink", Decimal("40"), 170),
        ("Mango Drink", "Mango drink", Decimal("45"), 160),
    ]

    for item_name, description, price, qty in menu_items:
        exists = db.execute(
            select(MenuItem).where(MenuItem.outlet_id == outlet.id, MenuItem.item_name == item_name)
        ).scalar_one_or_none()
        if not exists:
            db.add(
                MenuItem(
                    outlet_id=outlet.id,
                    item_name=item_name,
                    description=description,
                    price=price,
                    available_quantity=qty,
                    is_available=True,
                )
            )

    db.commit()