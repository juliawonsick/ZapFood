import hashlib
import hmac
import os
from typing import Optional
from fastapi import Header, HTTPException


def hash_senha(senha: str) -> str:
    senha = senha.strip()
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verificar_senha(senha: str, hash_: str) -> bool:
    senha = senha.strip()
    if hash_.startswith("pbkdf2_sha256$"):
        partes = hash_.split("$")
        if len(partes) != 3:
            return False
        _, salt, digest = partes
        novo = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 120_000).hex()
        return hmac.compare_digest(novo, digest)
    
    if hash_.startswith("$2"):
        try:
            from passlib.context import CryptContext
            ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return ctx.verify(senha, hash_)
        except Exception:
            return False
    return False


def get_usuario_atual(
    x_user_id:    Optional[str] = Header(None),
    x_user_perfil:Optional[str] = Header(None),
    x_user_nome:  Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return {
        "sub":    x_user_id,
        "perfil": x_user_perfil or "cliente",
        "nome":   x_user_nome   or "Usuário",
    }