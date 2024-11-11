import os
import redis
import socket
import logging
import logging.config
import time
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from typing import Any
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

# Konfiguracja trace'ów OpenTelemetry
provider = TracerProvider()
trace.set_tracer_provider(provider)

# Zdefiniowanie eksportera HTTP dla OpenTelemetry
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4318/v1/traces")
)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Inicjalizacja Tracer
tracer = trace.get_tracer(__name__)

# Filtr dla Trace ID
class TraceIDFilter(logging.Filter):
    def filter(self, record):
        # Pobiera bieżący trace ID z OpenTelemetry lub ustawia na '0' jeśli brak
        span = trace.get_current_span()
        trace_id = span.get_span_context().trace_id if span.get_span_context().trace_id else 0
        
        # Ustawia pusty Trace ID w logu, gdy wynosi 0, w przeciwnym razie formatuje go jako 32-znakowy heksadecymalny ciąg
        record.trace_id = f"[TraceID: {trace_id:032x}]" if trace_id != 0 else ""
        return True

# Konfiguracja loggera z opcjonalnym wyświetlaniem Trace ID w logach
LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"trace_id": {"()": TraceIDFilter}},
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(process)d] %(levelname)s %(trace_id)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["trace_id"],
            "level": "DEBUG",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    },
    "loggers": {
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        },
        "uvicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        }
    }
}

logging.config.dictConfig(LOG_CONFIG)
LOGGER = logging.getLogger("uvicorn.info")

# Log level setup
level = os.environ.get("LOG_LEVEL", "INFO")
if level == "INFO":
    LOGGER.setLevel(logging.INFO)
if level == "DEBUG":
    LOGGER.setLevel(logging.DEBUG)

# FastAPI i Redis konfiguracja
app = FastAPI()
hostname = socket.gethostname()
redis_host = os.environ.get("REDIS_HOST", "redis")
redis_port = int(os.environ.get("REDIS_PORT", 6379))

LOGGER.info(f"LOG_LEVEL has value {level}")
LOGGER.info(f"REDIS_HOST has value {redis_host}")
LOGGER.info(f"REDIS_PORT has value {redis_port}")

# Instrumentacja FastAPI i Redis
FastAPIInstrumentor.instrument_app(app)
RedisInstrumentor().instrument()

# Licznik żądań dla /api/v1/info
info_requests_counter = Counter('info_requests_total', 'Total number of requests to /api/v1/info')

class CustomJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        json_string = json.dumps(content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":"))
        return (json_string + "\n").encode("utf-8")

def get_redis():
    try:
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            socket_connect_timeout=3,  # Connection timeout in seconds
            socket_timeout=3  # Read/write timeout in seconds
        )
        r.ping()  # Test connection
        return r
    except (redis.ConnectionError, socket.gaierror) as e:
        LOGGER.error(f"Redis connection error: {e}")
        raise RuntimeError("Application cannot connect to Redis")

@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    # Rozpocznij nowy span jako bieżący kontekst
    with tracer.start_as_current_span("request_span") as span:
        trace_id = span.get_span_context().trace_id
        response = await call_next(request)
        if request.url.path == "/api/v1/info":
            info_requests_counter.inc()
        return response

@app.get("/", response_class=CustomJSONResponse)
async def root():
    LOGGER.info("Root endpoint accessed")
    return {"message": "Hello World", "hostname": hostname}

@app.get("/healthz", response_class=CustomJSONResponse)
async def healthz():
    try:
        r = get_redis()
        r.ping()
        LOGGER.info("Health check passed")
        return {"message": "Service is OK", "hostname": hostname}
    except (redis.ConnectionError, socket.gaierror) as e:
        LOGGER.error(f"Health check failed: {e}")
        return CustomJSONResponse(content={"message": "Service is NOT OK", "hostname": hostname}, status_code=500)
    except Exception as e:
        LOGGER.error(f"Unexpected error during health check: {e}")
        return CustomJSONResponse(content={"message": "Service is NOT OK", "hostname": hostname}, status_code=500)

@app.get("/api/v1/info", response_class=CustomJSONResponse)
async def info():
    try:
        started_at = time.time()
        r = get_redis()
        counter = r.get('counter')
        if counter is None:
            counter = 0
        else:
            counter = int(counter.decode('utf-8'))  # Decode and convert to integer
        LOGGER.info(f"Counter value: {counter}")
        duration = time.time() - started_at
        LOGGER.debug(f"Request took {duration} seconds")
        return {"message": "Counter", "hostname": hostname, "value": counter}
    except RuntimeError as e:
        LOGGER.error(f"Error in /api/v1/info: {e}")
        return CustomJSONResponse(content={"Can not connect to redis": str(e)}, status_code=500)

@app.post("/api/v1/info", response_class=CustomJSONResponse)
def info_post():
    try:
        started_at = time.time()
        r = get_redis()
        previous = r.get('counter')
        if previous is None:
            r.set('counter', 1)
        else:
            r.incr('counter')
        duration = time.time() - started_at
        LOGGER.debug(f"Request took {duration} seconds")
        LOGGER.info("Counter incremented")
        return {"message": "OK", "hostname": hostname}
    except RuntimeError as e:
        LOGGER.error(f"Error in /api/v1/info: {e}")
        return CustomJSONResponse(content={"Can not connect to redis": str(e)}, status_code=500)

@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    LOGGER.info("Metrics endpoint accessed")
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)