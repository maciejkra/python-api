FROM python:3-alpine
EXPOSE 5002
ENV LOG_LEVEL=INFO REDIS_HOST=redis REDIS_PORT=6379
WORKDIR /app
COPY ./ ./
RUN pip install --no-cache-dir -r requirements.txt
CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5002" ]
