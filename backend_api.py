import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from jose import jwt, JWTError

from Login.async_model import AsyncDBUserManager, get_db_dsn_from_env

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("SECRET_KEY", "devsecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

dsn = get_db_dsn_from_env() or "postgresql://myuser:mysecret@localhost:5432/mydb"
mgr = AsyncDBUserManager(dsn)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if SECRET_KEY == "devsecret":
        logger.warning("SECRET_KEY not set — using insecure default. Do NOT use in production.")
    await mgr.ensure_schema()
    yield


app = FastAPI(title="TPE Backend API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


class AuthIn(BaseModel):
    username: str
    password: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_username(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


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
async def me(username: str = Depends(get_current_username)):
    return {"username": username}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
