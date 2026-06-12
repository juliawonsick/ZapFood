# ZapFood

Sistema simples de delivery feito para a disciplina de Computacao Distribuida.

O projeto tem um frontend em HTML, CSS e JavaScript, e uma API em Python com FastAPI. A ideia e simular um pedido de comida passando por uma fila e tendo o status atualizado pela cozinha.

## Tecnologias usadas

- FastAPI: API REST do sistema.
- SQLite: cadastro e login dos usuarios.
- Redis: cache do cardapio e armazenamento temporario dos pedidos.
- RabbitMQ: fila onde os pedidos sao publicados.
- Docker Compose: sobe Redis e RabbitMQ.
- HTML, CSS e JavaScript: interface do cliente e da cozinha.

## Como rodar

Na pasta do projeto:

```bash
docker-compose up -d
```

Depois inicie a API:

```bash
uvicorn backend.main:app --reload
```

Acesse no navegador:

```text
http://127.0.0.1:8000
```

Painel do RabbitMQ:

```text
http://localhost:15672
usuario: guest
senha: guest
```

## Login da cozinha

```text
email: cozinha@zapfood.com
senha: cozinha123
```

## Como funciona

O cliente abre o cardapio, adiciona itens no carrinho e faz o pedido. A API valida os dados, calcula o total, salva o pedido no Redis e publica uma mensagem na fila do RabbitMQ.

O pedido e consumido por um worker. Para facilitar a apresentacao local, esse worker pode rodar embutido no backend. Tambem existe o arquivo `backend/worker.py`, que permite rodar o consumidor separado da API, mais parecido com a arquitetura base do trabalho.

A fila usa `prefetch_count=1`, ACK manual e Dead Letter Queue. Se ocorrer erro no processamento, a mensagem pode ser enviada para a fila morta.

Status do pedido:

```text
recebido -> confirmado -> preparando -> pronto -> entregando -> entregue

## Sobre login

Nesta versao o projeto nao usa JWT/token. O login retorna apenas o id, nome e perfil do usuario. O frontend envia essas informacoes em cabecalhos simples para a API.

Isso foi feito para deixar o trabalho mais facil de rodar e apresentar.

## Principais rotas

```text
POST /auth/cadastro
POST /auth/login
GET  /cardapio
POST /pedidos
GET  /pedidos/meus
DELETE /pedidos/{pedido_id}
GET  /cozinha/pedidos
PATCH /cozinha/pedidos/{pedido_id}
GET  /cozinha/fila
```

## Observacao

O cliente pode fazer mais de um pedido ao mesmo tempo. O frontend tambem evita recarregar o cardapio automaticamente para nao ficar mexendo os elementos da tela.
