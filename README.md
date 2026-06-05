# ZapFood

Sistema simples de delivery, o projeto tem por intuito simular um pedido no site de delivery.

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

O cliente abre o cardapio, adiciona itens no carrinho e faz o pedido. A API valida os dados, calcula o total, salva o pedido no Redis e envia uma mensagem para a fila do RabbitMQ.

Uma thread no backend consome essa fila e vai atualizando o status do pedido:

```text
recebido -> confirmado -> preparando -> pronto -> entregando -> entregue
```

O cliente consegue acompanhar os pedidos pela tela "Meus Pedidos". A cozinha consegue ver todos os pedidos e tambem alterar o status manualmente.

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
