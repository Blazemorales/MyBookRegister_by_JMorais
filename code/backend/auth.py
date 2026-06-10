"""Autenticação JWT compartilhada entre backend_api.py e cep_routes.py."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer


SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY env var é obrigatória. Gere com "
        "`python -c \"import secrets; print(secrets.token_hex(32))\"`."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# `db` injetado pelo backend_api.py no startup. Evita ciclo.
_db = None


def set_db(mgr) -> None:
    global _db
    _db = mgr


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Decodifica o JWT e retorna {username, user_id}."""
    if _db is None:
        raise RuntimeError("DB não inicializado para auth")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = await _db.get_user_id(username)
    if user_id is None:
        raise HTTPException(status_code=401, detail="User not found")
    return {"username": username, "user_id": user_id}


async def get_current_username(
    user: dict = Depends(get_current_user),
) -> str:
    return user["username"]
