from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
import httpx
import time
import logging
from collections import defaultdict

# =====================================================
# CONFIG
# =====================================================

SECRET_KEY = "super-secret-key"
ALGORITHM = "HS256"

app = FastAPI(title="Custom API Gateway")

# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# =====================================================
# RATE LIMITING
# =====================================================

RATE_LIMIT = 10
WINDOW_SIZE = 60

request_store = defaultdict(list)

# =====================================================
# SERVICES
# =====================================================

SERVICES = {
    "users": [
        "http://localhost:8001",
        "http://localhost:8002"
    ]
}

# =====================================================
# ROUND ROBIN
# =====================================================

rr_counter = defaultdict(int)


def get_next_server(service_name):
    servers = SERVICES[service_name]

    index = rr_counter[service_name]
    server = servers[index]

    rr_counter[service_name] = (
        index + 1
    ) % len(servers)

    return server


# =====================================================
# JWT VERIFY
# =====================================================

def verify_token(token):

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError as e:

        print("JWT ERROR:", e)

        raise HTTPException(
            status_code=401,
            detail="Invalid Token"
        )


# =====================================================
# RATE LIMIT CHECK
# =====================================================

def check_rate_limit(user_id):

    current_time = time.time()

    request_store[user_id] = [
        ts
        for ts in request_store[user_id]
        if current_time - ts < WINDOW_SIZE
    ]

    if len(request_store[user_id]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Rate Limit Exceeded"
        )

    request_store[user_id].append(current_time)


# =====================================================
# LOGGING MIDDLEWARE
# =====================================================

@app.middleware("http")
async def logger(request: Request, call_next):

    start = time.time()

    response = await call_next(request)

    duration = round(time.time() - start, 3)

    logging.info(
        f"{request.method} "
        f"{request.url.path} "
        f"{response.status_code} "
        f"{duration}s"
    )

    return response


# =====================================================
# LOGIN
# =====================================================

@app.post("/login")
async def login():

    payload = {
        "user_id": "user123"
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {
        "access_token": token
    }


# =====================================================
# ROOT
# =====================================================

@app.get("/")
async def root():

    return {
        "message": "Custom API Gateway Running"
    }


# =====================================================
# GATEWAY ROUTER
# =====================================================

@app.api_route(
    "/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
async def gateway(
    service: str,
    path: str,
    request: Request
):

    if service not in SERVICES:
        raise HTTPException(
            status_code=404,
            detail="Service Not Found"
        )

    auth_header = request.headers.get(
        "Authorization"
    )

    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authorization Header Missing"
        )

    try:
        scheme, token = auth_header.split()

        if scheme.lower() != "bearer":
            raise Exception()

    except:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization Header"
        )

    payload = verify_token(token)

    user_id = payload["user_id"]

    check_rate_limit(user_id)

    backend = get_next_server(service)

    target_url = f"{backend}/{path}"

    body = await request.body()

    async with httpx.AsyncClient() as client:

        response = await client.request(
            method=request.method,
            url=target_url,
            content=body,
            headers={
                k: v
                for k, v in request.headers.items()
                if k.lower() != "host"
            },
            params=request.query_params
        )

    try:
        data = response.json()
    except:
        data = {
            "response": response.text
        }

    return JSONResponse(
        status_code=response.status_code,
        content=data
    )


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "gateway:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )