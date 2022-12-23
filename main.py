from fastapi import FastAPI, Request
import redis
import socket
import logging
import os
import time

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {"default": {"format": "%(asctime)s [%(process)s] %(levelname)s: %(message)s"}},
    "handlers": {
        "console": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "level": "INFO",
        },
        "console": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "level": "DEBUG",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "uvicorn": {"propagate": True},
        "uvicorn.access": {"propagate": True},
        "uvicorn.error": {"propagate": True},
    },
}

logging.config.dictConfig(LOG_CONFIG)

LOGGER = logging.getLogger("uvicorn.info")

level = os.environ.get("LOG_LEVEL","INFO")
if level == "INFO":
    LOGGER.setLevel(logging.INFO)
if level == "DEBUG":
    LOGGER.setLevel(logging.DEBUG)


app = FastAPI()
hostname=socket.gethostname()
redis_host =  os.environ.get("REDIS_HOST","redis")
redis_port =  os.environ.get("REDIS_PORT",6379)
LOGGER.info(f"LOG_LEVEL has value {level}")
LOGGER.info(f"REDIS_HOST has value {redis_host}")
LOGGER.info(f"REDIS_PORT has value {redis_port}")

def get_redis():
    r = redis.Redis(host=redis_host, port=redis_port, db=0)
    return r

@app.get("/")
async def info():
    return {"message": "Hello World", "hostname": hostname}

@app.get("/healthz")
async def healthz():
    return {"message": "Service is OK", "hostname": hostname}

@app.get("/api/v1/info")
async def info():
    started_at = time.time()
    r = get_redis()
    counter =  r.get('counter')
    if counter is None:
        counter = 0
    LOGGER.info(f"counter var is {counter}")
    duration = time.time() - started_at
    LOGGER.debug(f"Request took {duration}")
    return {"message": "Counter", "hostname": hostname, "value": counter}

@app.post("/api/v1/info")
def info_post():
    started_at = time.time()
    r = get_redis()
    previous = r.get('counter')
    if previous is None:
        r.set('counter', 1)
    else:
        r.incr('counter')
    duration = time.time() - started_at
    LOGGER.debug(f"Request took {duration}")
    return {"message": "OK", "hostname": hostname}
