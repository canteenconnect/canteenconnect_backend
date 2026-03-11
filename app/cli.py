from decimal import Decimal

import click
from flask.cli import with_appcontext

from app import db
from app.models import (
    ROLE_ADMIN,
    ROLE_STUDENT,
    ROLE_SUPER_ADMIN,
    ROLE_VENDOR,
    Campus,
    MenuItem,
    Outlet,
    Role,
    User,
)


@click.command("seed-roles")
@with_appcontext
def seed_roles():
    roles = [
        (ROLE_STUDENT, "Student access"),
        (ROLE_VENDOR, "Vendor access"),
        (ROLE_ADMIN, "Admin access"),
        (ROLE_SUPER_ADMIN, "Super admin access"),
    ]
    created = 0
    for name, description in roles:
        existing = Role.query.filter_by(name=name).first()
        if existing:
            continue
        db.session.add(Role(name=name, description=description))
        created += 1
    if created:
        db.session.commit()
    click.echo(f"Roles seeded: {created}")


@click.command("create-superadmin")
@click.option("--email", required=True, help="Email for the super admin account.")
@click.option("--password", required=True, help="Password for the super admin account.")
@with_appcontext
def create_superadmin(email: str, password: str):
    role = Role.query.filter_by(name=ROLE_SUPER_ADMIN).first()
    if not role:
        role = Role(name=ROLE_SUPER_ADMIN, description="Super admin access")
        db.session.add(role)
        db.session.commit()

    user = User.query.filter_by(email=email.lower()).first()
    if user:
        user.role_id = role.id
        user.is_active = True
        user.set_password(password)
        db.session.commit()
        click.echo("Super admin updated.")
        return

    user = User(
        name="Super Admin",
        email=email.lower(),
        role_id=role.id,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo("Super admin created.")


def seed_demo_data() -> int:
    campus = Campus.query.filter_by(code="CANTEENCONNECT").first()
    if not campus:
        campus = Campus(name="CanteenConnect Campus", code="CANTEENCONNECT", location="Main Campus")
        db.session.add(campus)
        db.session.commit()

    outlet = Outlet.query.filter_by(campus_id=campus.id, name="Main Canteen").first()
    if not outlet:
        outlet = Outlet(name="Main Canteen", location="Campus Center", campus_id=campus.id)
        db.session.add(outlet)
        db.session.commit()

    items = [
        ("Veg Fried Rice", "Street-style vegetable fried rice with spring onions.", "110"),
        ("Egg Fried Rice", "Classic egg fried rice with pepper and soy flavor.", "130"),
        ("Chicken Fried Rice", "Wok-tossed fried rice with spicy chicken pieces.", "150"),
        ("Gobi Fried Rice", "Crispy gobi fried rice with indo-chinese masala.", "125"),
        ("Veg Noodles", "Hakka noodles loaded with fresh vegetables.", "105"),
        ("Egg Noodles", "Spicy noodles tossed with scrambled egg.", "125"),
        ("Chicken Noodles", "Chicken noodles with garlic-chilli wok flavor.", "145"),
        ("Gobi Noodles", "Crunchy gobi noodles with spicy sauce.", "120"),
        ("Veg Puff", "Flaky bakery puff filled with spicy veggies.", "35"),
        ("Egg Puff", "Golden puff pastry with masala egg filling.", "45"),
        ("Chicken Puff", "Bakery-style puff with spicy chicken mince.", "55"),
        ("Cola (300ml)", "Chilled cola served ice cold.", "40"),
        ("Lemon Soda", "Fresh lemon soda with a fizzy kick.", "35"),
        ("Orange Fizz", "Refreshing orange flavored cool drink.", "40"),
        ("Mango Drink", "Sweet chilled mango drink.", "45"),
    ]

    created = 0
    for name, description, price in items:
        existing = MenuItem.query.filter_by(outlet_id=outlet.id, name=name).first()
        if existing:
            continue
        db.session.add(
            MenuItem(
                outlet_id=outlet.id,
                name=name,
                description=description,
                price=Decimal(price),
                available_quantity=50,
                is_available=True,
            )
        )
        created += 1

    if created:
        db.session.commit()
    return created


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    created = seed_demo_data()
    click.echo(f"Demo menu items created: {created}")
