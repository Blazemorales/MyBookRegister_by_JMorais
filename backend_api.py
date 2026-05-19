import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import (
    create_access_token,
    get_current_user,
    set_db as set_auth_db,
)
from Login.async_model import AsyncDBUserManager, get_db_dsn_from_env
from cep_routes import router as cep_router, set_db_manager


logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

# Lista explícita de origens permitidas (CORS). Defina `ALLOWED_ORIGINS`
# separado por vírgula em prod; em dev cai para localhost.
_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]

dsn = get_db_dsn_from_env()
if not dsn:
    raise RuntimeError("DATABASE_URL/DATABASE_DSN env var é obrigatória.")
mgr = AsyncDBUserManager(dsn)
set_db_manager(mgr)
set_auth_db(mgr)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mgr.connect()
    await mgr.ensure_schema()
    try:
        yield
    finally:
        await mgr.close()


app = FastAPI(title="TPE Backend API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(cep_router)


class AuthIn(BaseModel):
    username: str
    password: str


@app.post("/register")
async def register(payload: AuthIn):
    try:
        await mgr.add_user(payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.post("/login")
async def login(payload: AuthIn):
    ok = await mgr.authenticate(payload.username, payload.password)
    if not ok:
        raise HTTPException(status_code=401, detail="invalid credentials")
    access_token = create_access_token({"sub": payload.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"username": user["username"]}


@app.get("/health")
async def health():
    """Liveness probe — não toca no banco."""
    return {"ok": True}


@app.get("/health/db")
async def health_db():
    try:
        ok = await mgr.ping()
        return {"ok": bool(ok)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"db unreachable: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
