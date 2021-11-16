from fastapi import FastAPI, Request
import redis
import socket
import logging
import os
import logging
import time

LOGGER = logging.getLogger("uvicorn.info")
level = os.environ.get("LOG_LEVEL","INFO")
if level == "INFO":
    LOGGER.setLevel(logging.INFO)
if level == "DEBUG":
    LOGGER.setLevel(logging.DEBUG)

hostname=socket.gethostname()

app = FastAPI()


def get_redis():
    redis_host =  os.environ.get("REDIS_HOST","redis")
    redis_port =  os.environ.get("REDIS_PORT",6379)
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
    r = get_redis()
    counter =  r.get('counter')
    if counter is None:
        counter = 0
    else:
        counter = counter.decode('utf-8')
    LOGGER.info('counter var is %s', counter)
    started_at = time.time()
    duration = time.time() - started_at
    LOGGER.debug('Request took %s', duration)
    return {"message": "Counter", "hostname": hostname, "value": counter}

@app.post("/api/v1/info")
def info_post():
    r = get_redis()
    previous = r.get('counter')
    if previous is None:
        r.set('counter', 1)
    else:
        r.incr('counter')
    return {"message": "OK", "hostname": hostname}