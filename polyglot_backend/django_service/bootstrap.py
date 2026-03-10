import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()
username = os.getenv("DJANGO_ADMIN_USERNAME", "admin")
password = os.getenv("DJANGO_ADMIN_PASSWORD", "Admin@12345")
email = os.getenv("DJANGO_ADMIN_EMAIL", "admin@canteen.local")

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Created Django superuser: {username}")
else:
    print(f"Django superuser already exists: {username}")