FROM python:3.13-slim

WORKDIR /app
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app
RUN pip install --no-cache-dir /app/backend
COPY alembic.ini /app/alembic.ini
COPY database/migrations /app/database/migrations
COPY tester /app/tester

ENV PYTHONPATH=/app:/app/backend
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
