FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY django_service/requirements.txt /app/django_service/requirements.txt
RUN pip install --no-cache-dir -r /app/django_service/requirements.txt

COPY . /app

EXPOSE 8003
CMD ["sh", "-c", "python django_service/manage.py migrate --noinput && python django_service/bootstrap.py && gunicorn config.wsgi:application --chdir django_service --bind 0.0.0.0:8003 --workers 2"]