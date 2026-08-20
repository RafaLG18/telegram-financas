# Decisões

Uma seção por decisão que não é óbvia: o contexto, a escolha, e o que foi
descartado. Se você for mudar uma delas, é aqui que está o motivo de ela existir.

## Valor em centavos inteiros, sempre positivo

`Transacao.valor_centavos` é `int` e tem `CheckConstraint("valor_centavos > 0")`.
O sinal do lançamento vem de `tipo` (`gasto` / `entrada`), não do número.

Float erra centavo em soma de relatório, e relatório que não fecha destrói a
confiança no bot inteiro. Guardar o sinal no valor pareceria mais simples, mas
espalharia `abs()` por toda formatação e deixaria `-0` e `+0` representáveis.

**Descartado:** `Decimal` no banco (o SQLite não tem tipo decimal nativo — viraria
texto ou float de qualquer jeito). O `Decimal` é usado, mas só dentro do
`parse.py`, na conversão para centavos.

## `data` separada de `criado_em`

`data` é a data do fato, no fuso local; `criado_em` é o instante do registro, em
UTC. São coisas diferentes: você lança no domingo o que gastou na sexta.

Consequência prática: "hoje" sempre sai de `dt.datetime.now(config.tz).date()`,
nunca de `date.today()` — o container roda em UTC e o mês fecharia errado por
três horas todo dia.

## `origem_update_id` UNIQUE

O Telegram reenvia updates quando não recebe confirmação. Sem defesa, um
`50 mercado` vira dois lançamentos, e o usuário só descobre no fim do mês.

`registrar_transacao` checa o `origem_update_id` antes de inserir e devolve
`(transacao, criada)`; o `IntegrityError` do UNIQUE é a rede de proteção para a
corrida. O handler que recebe `criada=False` sai calado — responder de novo
seria pior que o silêncio.

Por isso o polling **não** usa `drop_pending_updates`: o UNIQUE já protege, e
assim nada que você mandou com o bot fora do ar se perde.

## Rascunho no banco, não em memória

O fluxo guiado precisa carregar estado entre mensagens. Um dict em memória seria
uma linha de código.

Duas coisas o derrubam: o estado morre em todo restart (e o bot reinicia a cada
deploy, no meio do seu lançamento), e o `callback_data` do Telegram tem limite de
64 bytes — precisamos de um id curto que aponte para o dado, e um id só existe
se algo o persistir. `Rascunho.id` é `secrets.token_hex(4)`.

Rascunhos abandonados são limpos no boot, acima de 24h.

## Editar a mensagem removendo o teclado

Toda resposta a callback reescreve a mensagem sem os botões. O Telegram guarda a
conversa para sempre: sem isso, o botão de um lançamento de três dias atrás
continua clicável, e ninguém lembra o que ele confirmava.

## SQLAlchemy síncrono num bot async

Usuário único, SQLite local: cada operação custa microssegundos, e o event loop
não sofre. `aiosqlite` exigiria o template async do Alembic e uma sessão async
em todo handler, sem comprar nada.

## Uma réplica, sempre

Dois pollers no mesmo token = `409 Conflict` no `getUpdates`, e o SQLite aceita
um escritor só. Isso não é convenção: o chart **falha no render** se
`replicaCount > 1` ou se o `accessMode` não for `ReadWriteOnce`, antes de chegar
no cluster.

## `render_as_batch=True` no Alembic

O SQLite quase não tem `ALTER TABLE`. Sem o modo batch, o autogenerate produz
migração que só falha na hora de aplicar — o erro aparece longe da causa.

## Parsing por regra, sem LLM

`parse.py` é regex e `Decimal`: determinístico, testável e instantâneo. Um
lançamento errado por interpretação criativa custa mais caro que um "não
entendi" honesto — e o fluxo guiado sempre está ali como caminho principal.

## Whitelist de um chat_id

Bot do Telegram é público por padrão: qualquer um que descubra o @ conversa com
ele. `SomenteDono` é a única coisa entre suas finanças e um estranho. Sem
`OWNER_CHAT_ID` configurado o bot não processa nada — só informa qual é o seu
`chat_id`, para você preencher e reiniciar.

## Token por Secret, nunca por `--set`

`scripts/deploy.sh` aplica o Secret por stdin. Um `--set telegram.botToken=...`
viraria argumento de processo (visível no `ps`) e ficaria no histórico do
release, que `helm get values` lê em texto puro.

Pelo mesmo motivo o `.env` é lido por regex e não por `source`: arquivo de
configuração não deveria poder executar comando.

## Uma imagem só, do build ao registry

O CI builda uma vez e é a mesma imagem que passa pelo scan, pelo smoke test e
vai para o GHCR. Scan em artefato diferente do que entra em produção não prova
nada.

## Fora do escopo da v1

Contas (a coluna `conta_id` já existe, nula), orçamento por categoria, tags,
recorrência, edição de lançamento (só `/desfazer`), anexo/OCR de nota.
