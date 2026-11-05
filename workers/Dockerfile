FROM python:3.13-slim

WORKDIR /app
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app
RUN pip install --no-cache-dir '/app/backend[blackbox]'
RUN python -m playwright install --with-deps chromium
COPY tester /app/tester
COPY workers /app/workers

ENV PYTHONPATH=/app:/app/backend
CMD ["python", "-m", "workers.main"]
