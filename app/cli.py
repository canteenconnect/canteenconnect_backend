import click
from flask.cli import with_appcontext

from app import db
from app.models import ROLE_ADMIN, ROLE_STUDENT, ROLE_SUPER_ADMIN, ROLE_VENDOR, Role


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
