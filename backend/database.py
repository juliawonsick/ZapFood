import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "zapfood.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nome       TEXT    NOT NULL,
            email      TEXT    NOT NULL UNIQUE,
            senha_hash TEXT    NOT NULL,
            perfil     TEXT    NOT NULL DEFAULT 'cliente',
            criado_em  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # Verifica se a cozinha já existe — só insere se não existir
    # NUNCA faz UPDATE do hash, senão invalida a senha a cada restart
    existente = cur.execute(
        "SELECT id FROM usuarios WHERE email = ?", ("cozinha@zapfood.com",)
    ).fetchone()

    if not existente:
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from auth import hash_senha
        cur.execute("""
            INSERT INTO usuarios (nome, email, senha_hash, perfil)
            VALUES (?, ?, ?, ?)
        """, ("Cozinha Admin", "cozinha@zapfood.com", hash_senha("cozinha123"), "cozinha"))
        print("[OK] Usuario cozinha criado")
    else:
        print("[OK] Usuario cozinha ja existe")

    conn.commit()
    conn.close()
    print("[OK] Banco SQLite inicializado")


def criar_usuario(nome: str, email: str, senha_hash: str, perfil: str = "cliente"):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?,?,?,?)",
            (nome, email, senha_hash, perfil)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def buscar_usuario_por_email(email: str):
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM usuarios WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def buscar_usuario_por_id(uid: int):
    conn = get_conn()
    row  = conn.execute(
        "SELECT id, nome, email, perfil, criado_em FROM usuarios WHERE id = ?", (uid,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None