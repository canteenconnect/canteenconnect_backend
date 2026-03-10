FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY flask_service/requirements.txt /app/flask_service/requirements.txt
RUN pip install --no-cache-dir -r /app/flask_service/requirements.txt

COPY . /app

EXPOSE 8002
CMD ["python", "flask_service/app.py"]