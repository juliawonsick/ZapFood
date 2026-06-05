"""
ZapFood — Backend Completo
Disciplina: Computação Distribuída (CCOM4N)
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from typing import Optional
import redis, pika, json, uuid, threading, time
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

import database as db
import auth
from cardapio_data import CARDAPIO


app = FastAPI(title="ZapFood API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def servir_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/app.js", include_in_schema=False)
def servir_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.js"))


@app.get("/style.css", include_in_schema=False)
def servir_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))


try:
    rc = redis.Redis(host="localhost", port=6379, decode_responses=True)
    rc.ping()
    print("[OK] Redis conectado")
except Exception as e:
    print(f"[ERRO] Redis: {e}")
    rc = None


FILA = "fila_pedidos"


def rabbit_channel():
    conn = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    ch = conn.channel()
    ch.queue_declare(queue=FILA, durable=True)
    return conn, ch


def publicar(pedido: dict):
    try:
        conn, ch = rabbit_channel()
        ch.basic_publish(
            exchange="",
            routing_key=FILA,
            body=json.dumps(pedido),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        conn.close()
        print(f"[FILA] Publicado na fila: {pedido['id'][:8]}")
    except Exception as e:
        print(f"[ERRO] RabbitMQ publish: {e}")


def processar_pedido(pedido: dict):
    pid = pedido["id"]

    etapas = [
        ("confirmado", 8),
        ("preparando", 20),
        ("pronto", 10),
        ("entregando", 15),
        ("entregue", 0),
    ]

    for status, espera in etapas:
        time.sleep(espera)

        if rc:
            raw = rc.get(f"pedido:{pid}")

            if raw:
                dados = json.loads(raw)

                if dados["status"] == "cancelado":
                    return

                agora = datetime.now().strftime("%H:%M:%S")
                dados["status"] = status
                dados["atualizado_em"] = agora

                historico = dados.get("historico", [])
                historico.append({"status": status, "hora": agora})
                dados["historico"] = historico

                rc.setex(f"pedido:{pid}", 86400, json.dumps(dados))

        print(f"[PEDIDO] {pid[:8]} -> {status}")


def consumer_loop():
    while True:
        try:
            conn, ch = rabbit_channel()

            def callback(ch, method, props, body):
                pedido = json.loads(body)
                ch.basic_ack(delivery_tag=method.delivery_tag)

                threading.Thread(
                    target=processar_pedido,
                    args=(pedido,),
                    daemon=True
                ).start()

            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue=FILA, on_message_callback=callback)

            print("[OK] RabbitMQ consumer aguardando...")
            ch.start_consuming()

        except Exception as e:
            print(f"[ERRO] Consumer: {e}. Reconectando em 5s...")
            time.sleep(5)


threading.Thread(target=consumer_loop, daemon=True).start()


def cache_cardapio():
    if rc:
        rc.setex("cardapio", 120, json.dumps(CARDAPIO))
        print("[CACHE] Cardapio em cache (TTL 120s)")


cache_cardapio()


@app.on_event("startup")
def startup():
    db.init_db()


class CadastroInput(BaseModel):
    nome: str
    email: str
    senha: str

    @field_validator("nome")
    @classmethod
    def nome_valido(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Nome deve ter ao menos 3 caracteres")
        if len(v) > 60:
            raise ValueError("Nome muito longo")
        return v

    @field_validator("email")
    @classmethod
    def email_valido(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("E-mail inválido")
        return v

    @field_validator("senha")
    @classmethod
    def senha_valida(cls, v):
        if len(v) < 6:
            raise ValueError("Senha deve ter ao menos 6 caracteres")
        return v


class LoginInput(BaseModel):
    email: str
    senha: str

    @field_validator("email")
    @classmethod
    def email_fmt(cls, v):
        return v.strip().lower()


class ItemPedido(BaseModel):
    produto_id: int
    quantidade: int
    observacao: Optional[str] = ""

    @field_validator("quantidade")
    @classmethod
    def qtd_valida(cls, v):
        if v < 1:
            raise ValueError("Quantidade deve ser ao menos 1")
        if v > 20:
            raise ValueError("Quantidade máxima por item: 20")
        return v

    @field_validator("observacao")
    @classmethod
    def obs_valida(cls, v):
        if v and len(v) > 100:
            raise ValueError("Observação muito longa")
        return v.strip() if v else ""


class NovoPedido(BaseModel):
    endereco: str
    itens: list[ItemPedido]
    observacao: Optional[str] = ""

    @field_validator("endereco")
    @classmethod
    def end_valido(cls, v):
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Endereço muito curto")
        if len(v) > 200:
            raise ValueError("Endereço muito longo")
        return v

    @field_validator("itens")
    @classmethod
    def itens_validos(cls, v):
        if not v:
            raise ValueError("O pedido precisa ter ao menos 1 item")
        if len(v) > 20:
            raise ValueError("Máximo de 20 itens diferentes por pedido")
        return v

    @field_validator("observacao")
    @classmethod
    def obs_valida(cls, v):
        if v and len(v) > 200:
            raise ValueError("Observação muito longa")
        return v.strip() if v else ""


class AtualizarStatus(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_valido(cls, v):
        validos = [
            "confirmado",
            "preparando",
            "pronto",
            "entregando",
            "entregue",
            "cancelado",
        ]

        if v not in validos:
            raise ValueError(f"Status inválido. Use: {validos}")

        return v


def salvar_pedido_redis(pedido: dict):
    rc.setex(f"pedido:{pedido['id']}", 86400, json.dumps(pedido))
    rc.lpush("pedidos_ids", pedido["id"])
    rc.ltrim("pedidos_ids", 0, 199)


def get_cardapio_cache() -> dict:
    raw = rc.get("cardapio") if rc else None
    itens = json.loads(raw) if raw else CARDAPIO
    return {i["id"]: i for i in itens}


@app.post("/auth/cadastro", status_code=201)
def cadastro(dados: CadastroInput):
    hash_ = auth.hash_senha(dados.senha)

    ok = db.criar_usuario(dados.nome, dados.email, hash_)

    if not ok:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    usuario = db.buscar_usuario_por_email(dados.email)

    return {
        "perfil": usuario["perfil"],
        "nome": usuario["nome"],
        "id": usuario["id"],
    }


@app.post("/auth/login")
def login(dados: LoginInput):
    usuario = db.buscar_usuario_por_email(dados.email)

    if not usuario or not auth.verificar_senha(dados.senha, usuario["senha_hash"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")

    return {
        "perfil": usuario["perfil"],
        "nome": usuario["nome"],
        "id": usuario["id"],
    }


@app.get("/auth/me")
def me(usuario=Depends(auth.get_usuario_atual)):
    usuario_id = int(usuario["sub"])

    dados = db.buscar_usuario_por_id(usuario_id)

    if rc:
        raw = rc.get(f"enderecos:{usuario_id}")
        dados["enderecos_salvos"] = json.loads(raw) if raw else []

    return dados


@app.post("/auth/enderecos")
def salvar_endereco(body: dict, usuario=Depends(auth.get_usuario_atual)):
    usuario_id = int(usuario["sub"])

    endereco = (body.get("endereco") or "").strip()

    if len(endereco) < 10:
        raise HTTPException(400, "Endereço muito curto")

    if not rc:
        raise HTTPException(503, "Redis indisponível")

    key = f"enderecos:{usuario_id}"

    raw = rc.get(key)
    lista = json.loads(raw) if raw else []

    if endereco not in lista:
        lista.insert(0, endereco)
        lista = lista[:3]
        rc.set(key, json.dumps(lista))

    return {"enderecos": lista}


@app.get("/auth/enderecos")
def listar_enderecos(usuario=Depends(auth.get_usuario_atual)):
    usuario_id = int(usuario["sub"])

    if not rc:
        raise HTTPException(503, "Redis indisponível")

    raw = rc.get(f"enderecos:{usuario_id}")

    return {"enderecos": json.loads(raw) if raw else []}


@app.get("/cardapio")
def listar_cardapio():
    if not rc:
        raise HTTPException(503, "Redis indisponível")

    raw = rc.get("cardapio")
    ttl = rc.ttl("cardapio")

    if raw:
        return {
            "fonte": "redis_cache",
            "ttl": ttl,
            "itens": json.loads(raw),
        }

    cache_cardapio()

    return {
        "fonte": "recarregado",
        "ttl": 120,
        "itens": CARDAPIO,
    }


@app.post("/pedidos", status_code=201)
def criar_pedido(dados: NovoPedido, usuario=Depends(auth.get_usuario_atual)):
    if not rc:
        raise HTTPException(503, "Redis indisponível")

    cliente_id = int(usuario["sub"])

    catalogo = get_cardapio_cache()

    itens_pedido = []
    total = 0.0
    ids_vistos = set()

    for item in dados.itens:
        if item.produto_id not in catalogo:
            raise HTTPException(
                400,
                f"Produto {item.produto_id} não existe no cardápio"
            )

        if item.produto_id in ids_vistos:
            raise HTTPException(
                400,
                "Produto duplicado no pedido. Ajuste a quantidade"
            )

        ids_vistos.add(item.produto_id)

        produto = catalogo[item.produto_id]
        subtotal = round(produto["preco"] * item.quantidade, 2)
        total += subtotal

        itens_pedido.append({
            "produto_id": item.produto_id,
            "nome": produto["nome"],
            "emoji": produto["emoji"],
            "quantidade": item.quantidade,
            "preco_unitario": produto["preco"],
            "subtotal": subtotal,
            "observacao": item.observacao,
        })

    agora = datetime.now().strftime("%H:%M:%S")

    qtd_total = sum(i.quantidade for i in dados.itens)
    tempo_estimado = 30 + (qtd_total // 3) * 5

    pedido = {
        "id": str(uuid.uuid4()),
        "cliente_id": cliente_id,
        "cliente_nome": usuario["nome"],
        "endereco": dados.endereco,
        "observacao": dados.observacao,
        "itens": itens_pedido,
        "total": round(total, 2),
        "status": "recebido",
        "tempo_estimado": tempo_estimado,
        "criado_em": agora,
        "atualizado_em": agora,
        "historico": [
            {
                "status": "recebido",
                "hora": agora,
            }
        ],
    }

    salvar_pedido_redis(pedido)
    publicar(pedido)

    key = f"enderecos:{cliente_id}"

    raw_end = rc.get(key)
    lista_end = json.loads(raw_end) if raw_end else []

    if dados.endereco not in lista_end:
        lista_end.insert(0, dados.endereco)
        rc.set(key, json.dumps(lista_end[:3]))

    return {
        "mensagem": "Pedido criado!",
        "pedido_id": pedido["id"],
        "total": pedido["total"],
        "tempo_estimado": tempo_estimado,
    }


@app.get("/pedidos/meus")
def meus_pedidos(usuario=Depends(auth.get_usuario_atual)):
    if not rc:
        raise HTTPException(503, "Redis indisponível")

    cliente_id = int(usuario["sub"])

    ids = rc.lrange("pedidos_ids", 0, 199)
    result = []

    for pid in ids:
        raw = rc.get(f"pedido:{pid}")

        if raw:
            p = json.loads(raw)

            if p.get("cliente_id") == cliente_id:
                result.append(p)

    return {"pedidos": result}


@app.delete("/pedidos/{pedido_id}")
def cancelar_pedido(pedido_id: str, usuario=Depends(auth.get_usuario_atual)):
    if not rc:
        raise HTTPException(503, "Redis indisponível")

    cliente_id = int(usuario["sub"])

    raw = rc.get(f"pedido:{pedido_id}")

    if not raw:
        raise HTTPException(404, "Pedido não encontrado")

    p = json.loads(raw)

    if p.get("cliente_id") != cliente_id and usuario["perfil"] != "cozinha":
        raise HTTPException(403, "Sem permissão para cancelar este pedido")

    if p["status"] in ("preparando", "pronto", "entregando", "entregue"):
        raise HTTPException(
            400,
            f"Não é possível cancelar: pedido está '{p['status']}'"
        )

    p["status"] = "cancelado"
    p["atualizado_em"] = datetime.now().strftime("%H:%M:%S")

    rc.setex(f"pedido:{pedido_id}", 86400, json.dumps(p))

    return {"mensagem": "Pedido cancelado"}


@app.get("/cozinha/pedidos")
def cozinha_pedidos(usuario=Depends(auth.get_usuario_atual)):
    if usuario["perfil"] != "cozinha":
        raise HTTPException(403, "Acesso restrito à cozinha")

    if not rc:
        raise HTTPException(503, "Redis indisponível")

    ids = rc.lrange("pedidos_ids", 0, 199)
    result = []

    for pid in ids:
        raw = rc.get(f"pedido:{pid}")

        if raw:
            result.append(json.loads(raw))

    return {"pedidos": result}


@app.patch("/cozinha/pedidos/{pedido_id}")
def cozinha_atualizar(
    pedido_id: str,
    dados: AtualizarStatus,
    usuario=Depends(auth.get_usuario_atual)
):
    if usuario["perfil"] != "cozinha":
        raise HTTPException(403, "Acesso restrito à cozinha")

    if not rc:
        raise HTTPException(503, "Redis indisponível")

    raw = rc.get(f"pedido:{pedido_id}")

    if not raw:
        raise HTTPException(404, "Pedido não encontrado")

    p = json.loads(raw)

    agora = datetime.now().strftime("%H:%M:%S")

    p["status"] = dados.status
    p["atualizado_em"] = agora

    historico = p.get("historico", [])
    historico.append({
        "status": dados.status,
        "hora": agora,
    })

    p["historico"] = historico

    rc.setex(f"pedido:{pedido_id}", 86400, json.dumps(p))

    return {
        "mensagem": f"Status atualizado para '{dados.status}'",
        "pedido": p,
    }


@app.get("/cozinha/fila")
def cozinha_fila(usuario=Depends(auth.get_usuario_atual)):
    if usuario["perfil"] != "cozinha":
        raise HTTPException(403, "Acesso restrito à cozinha")

    try:
        conn, ch = rabbit_channel()

        q = ch.queue_declare(
            queue=FILA,
            durable=True,
            passive=True
        )

        msgs = q.method.message_count

        conn.close()

        return {
            "fila": FILA,
            "mensagens_pendentes": msgs,
        }

    except Exception as e:
        return {"erro": str(e)}
