import click
from flask.cli import with_appcontext

from app import db
from app.models import ROLE_ADMIN, ROLE_STUDENT, ROLE_SUPER_ADMIN, ROLE_VENDOR, Role, User


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
