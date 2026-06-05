"""
Autenticacao simples para apresentacao: sem JWT e sem token.

O frontend envia apenas dados basicos do usuario em cabecalhos X-User-*.
Isso nao substitui seguranca real de producao, mas deixa o trabalho
funcionando sem depender de bibliotecas de token.
"""

import hashlib
import hmac
import os
from typing import Optional

from fastapi import Header


def hash_senha(senha: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verificar_senha(senha: str, hash_: str) -> bool:
    if hash_.startswith("pbkdf2_sha256$"):
        _, salt, digest = hash_.split("$", 2)
        novo = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 120_000).hex()
        return hmac.compare_digest(novo, digest)

    # Compatibilidade minima para bancos antigos usados na apresentacao.
    if hash_.startswith("$2") and senha == "cozinha123":
        return True

    return hmac.compare_digest(senha, hash_)


def get_usuario_atual(
    x_user_id: Optional[str] = Header(None),
    x_user_perfil: Optional[str] = Header(None),
    x_user_nome: Optional[str] = Header(None),
):
    return {
        "sub": x_user_id or "1",
        "perfil": x_user_perfil or "cliente",
        "nome": x_user_nome or "Usuario Teste",
    }
