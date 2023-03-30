# syntax=docker/dockerfile:1
# Base stage
FROM python:3-alpine AS base
EXPOSE 5002
ENV LOG_LEVEL=INFO REDIS_HOST=redis REDIS_PORT=6379
WORKDIR /app

COPY requirements.txt main.py .
RUN pip install --no-cache-dir -r requirements.txt

# Test stage
FROM base AS test

COPY requirements_test.txt test_my_app.py .
RUN pip install --no-cache-dir -r requirements_test.txt

RUN pytest test_my_app.py  

# Production stage
FROM base AS production


HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 CMD [ "curl", "localhost:5002/healthz" ]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5002"]
