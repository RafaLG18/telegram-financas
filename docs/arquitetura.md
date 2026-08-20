# Arquitetura

O *porquê* de cada escolha está em [Decisões](decisoes.md); aqui é o *como*.

```
Telegram ──polling──> handlers/  ──> core/   ──> SQLite
                      (aiogram)      (regras)    (SQLAlchemy + Alembic)
```

## A fronteira

`core/` não importa aiogram. É a única fronteira arquitetural do projeto, e é o
que permite testar as regras sem subir bot e trocar de interface depois. Dentro
dele, um módulo por domínio — `categorias`, `transacoes`, `relatorios`,
`rascunhos` — e o `__init__` re-exporta a API pública, então importar do pacote
ou do módulo específico dá no mesmo.

Regra nova de negócio entra em `core/`. Handler só traduz Telegram ↔ core.

## Módulos

| Arquivo | Papel |
|---|---|
| `bot.py` | ponto de entrada: config, banco, health server, polling |
| `middlewares.py` | `SomenteDono` — a whitelist de um chat_id só |
| `handlers/` | tradução Telegram ↔ core, um router por área |
| `core/` | regras de negócio, sem aiogram |
| `models.py` | tabelas e estados do fluxo guiado |
| `db.py` | engine, `session_scope`, pragmas do SQLite |
| `parse.py` | texto livre → valor, data, descrição (determinístico, sem LLM) |
| `textos.py` | formatação das mensagens |
| `keyboards.py` | teclados inline e constantes de `callback_data` |
| `config.py` | ambiente → `Config`, falhando cedo |
| `health.py` | `/healthz` e `/readyz` |

## O caminho de um update

1. **Middleware.** `SomenteDono` compara o `chat_id` com `OWNER_CHAT_ID`; o que
   não bate é descartado com log. Sem `OWNER_CHAT_ID` o bot entra em modo
   bootstrap: só responde qual é o seu `chat_id`. O `update_id` é injetado em
   `data` aqui — é dele que vem a idempotência.
2. **Router.** `handlers/__init__.py::montar_router` inclui `start`,
   `registrar`, `relatorios` e, **por último**, `rapido`. A ordem importa:
   `rapido` é catch-all de texto (`F.text & ~F.text.startswith("/")`) e só pode
   receber o que ninguém mais quis. Router novo entra antes dele.
3. **Handler.** Abre `session_scope()`, chama o `core`, extrai o texto da
   resposta ainda dentro do bloco e só então dá `await` no Telegram.
4. **Core.** `registrar_transacao` devolve `(transacao, criada)`. `criada=False`
   significa update reenviado: o handler sai calado, sem duplicar nem confundir.

## Os dois caminhos de registro

| Caminho | Como funciona |
|---|---|
| `/registrar` | fluxo guiado; um `Rascunho` no banco carrega o estado (`E_TIPO` → `E_VALOR` → `E_CATEGORIA` → `E_CONFIRMACAO`, com desvio para `E_DATA_LIVRE`) |
| `50 mercado` | `handlers/rapido.py`: `parse_lancamento` extrai valor e data, o resto vira descrição e tenta casar com uma categoria pelo nome |

O `callback_data` do Telegram tem limite duro de 64 bytes, então os botões
carregam só ponteiros curtos (`acao:rascunho_id:valor`) — o dado real vive no
banco. Toda resposta a callback edita a mensagem removendo o teclado, o que
mata o "botão zumbi" clicado dias depois.

## Acesso ao banco

`db.py` guarda engine e sessionmaker em módulo global; `init_engine()` precisa
ter rodado antes (`bot.py::preparar_banco`, que também faz o seed de categorias
e limpa rascunhos abandonados). Handlers usam:

```python
with session_scope() as sessao:   # commit no sucesso, rollback na exceção
    ...
```

Objetos são `expire_on_commit=False`, mas **extraia o que vai para a resposta
(texto, ids) dentro do bloco**, antes do `await`.

Pragmas ligados em toda conexão: `journal_mode=WAL` (backup e leitura enquanto o
bot escreve), `foreign_keys=ON` (o SQLite ignora FK por padrão — sem isso as
`ForeignKey` do modelo são decorativas) e `busy_timeout=5000`.

## Modelo de dados

- `categoria` — nome único, `tipo` em `gasto`/`entrada`/`ambos`, `ativa`.
- `transacao` — `valor_centavos` sempre positivo (o sinal vem de `tipo`), `data`
  do fato e `criado_em` do registro, `origem_update_id` UNIQUE, `conta_id`
  reservado para a v2.
- `rascunho` — lançamento em construção, id curto de 8 hex, apagado ao concluir
  e após 24h de abandono.
