# Cota por membro na cobranca V2 — desenho

Regra do dono (18/10/2026, item 6): a sessao de um profissional so e
bloqueada por DOIS motivos — o limite que o responsavel atribuiu a ele, ou o
esgotamento total dos creditos da clinica. Sem limite atribuido, o
profissional consome do pool da clinica ate ele acabar.

## O que esta instalado

| Caminho | Pool da clinica | Limite por membro |
|---|---|---|
| V1 (`migrations/010`, funcao de evento de credito) | bloqueia em `insufficient organization credits` | bloqueia em `member quota exhausted` quando ha linha em `organization_member_quotas`; sem linha, so o pool |
| V2 (`migrations/047` + `050`, `psique_v2_session_charge`) | sem saldo a sessao fica PENDENTE e liquida depois (FIFO) | **nao consulta** `organization_member_quotas` |

Producao em 18/10/2026: 9 carteiras em V2, 3 em V1; `organization_member_quotas`
vazia (nenhum limite atribuido ate hoje). A regra do dono e exatamente a do
V1; o V2 cumpre so a metade do pool, e nem essa bloqueia — enfileira.

## O que entra (migration 052)

1. `psique_v2_session_charge` ganha a checagem do limite por membro, copiando
   a definicao corrente da 050 **verbatim** mais o bloco novo (regra da
   secao 9: so uma migration mexe nessa funcao por vez).
2. O limite conta a sessao no momento em que ela e ACEITA (cobrada ou
   pendente), porque a sessao aconteceu; recusa com `PSIQUE_MEMBER_QUOTA_EXHAUSTED`
   quando `consumed_sessions + 1 > quota_sessions`. Idempotente por
   `session_id`, como o resto da funcao.
3. Sem linha de cota para o membro: comportamento atual (pool).
4. A rota PUT de cota (`main.py`, `credits.manage`) continua a mesma.

## Decisoes do dono antes de comecar

| Decisao | Opcao recomendada |
|---|---|
| Sessao pendente (sem saldo no pool) conta na cota do membro? | Sim: a sessao foi realizada; a cota e de sessoes, nao de creditos |
| Pool esgotado bloqueia a sessao ou deixa pendente, como hoje no V2? | Manter pendente (decisao da Fase 7 do Psique); a regra "esgotamento total bloqueia" fica satisfeita quando a pendencia nao pode ser aberta — confirmar se e isso que o dono quer |

## Prova

Contra PostgreSQL real, Windows e Linux (secao 8): membro com cota 2 faz a
terceira e recebe o erro nomeado; membro sem cota segue; reaplicar a
migration e no-op; a 052 aplica incremental sobre um banco em 051.
