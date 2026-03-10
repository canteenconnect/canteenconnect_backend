FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY fastapi_service/requirements.txt /app/fastapi_service/requirements.txt
RUN pip install --no-cache-dir -r /app/fastapi_service/requirements.txt

COPY . /app

EXPOSE 8001
CMD ["uvicorn", "fastapi_service.main:app", "--host", "0.0.0.0", "--port", "8001"]