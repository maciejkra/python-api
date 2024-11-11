# syntax=docker/dockerfile:1
FROM python:3-alpine
EXPOSE 5002
ENV LOG_LEVEL=INFO REDIS_HOST=redis REDIS_PORT=6379 OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
WORKDIR /app
COPY ./main.py ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && apk add --no-cache curl 
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 CMD [ "curl", "localhost:5002/healthz" ]
CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5002" ]
