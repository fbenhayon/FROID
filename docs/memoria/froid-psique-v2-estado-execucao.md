---
name: froid-psique-v2-estado-execucao
description: "Psique V2: Fases 1, 2A e 2B commitadas em 29/09/2026; Sandbox QA acct_1UL3JIAg9NSIrvBV; homologação com cartão pendente; 2C exige nova aprovação; PostgreSQL de teste se recria, nunca se sonda"
metadata:
  node_type: memory
  type: project
  originSessionId: 6ec3bea4-fdce-409b-b3dd-be8966cb8ab3
  modified: 2026-09-29T20:48:57.714Z
---

Em 29/09/2026, com autorização do Fábio, o Psique V2 entrou no `main` em três commits cirúrgicos: `3732d6c9` (auditoria de pré-implementação), `3d570799` (Fase 1: migrations explícitas + catálogo em rascunho) e `55462af6` (Fase 2A: trial, máquina de créditos, identidade de fonte), seguidos de `c1405a6f` (registros de sessão). A frente das derivadas ([[froid-derivadas-zeradas-decisao-adiada]]) foi preservada **sem instalar** na branch `frente-derivadas-zeradas` (`8b29de78`) — instalar = merge deliberado + janela de rebuild. Tudo foi **enviado ao origin** no mesmo dia; a árvore ficou limpa. Pendências: o `git stash drop stash@{0}` ficou para o Fábio (backup provado idêntico a `e0694150`; o classificador bloqueou o descarte por mim); produção segue intocada.

**Fase 2B (Stripe TEST), autorizada, executada e commitada em 29/09/2026** (`16d0f28d`, 15 arquivos): migration 039, `psique_billing.py`, `psique_api.py`, ferramenta de mappings; 117 testes Psique verdes. Sandbox dedicado `acct_1UL3JIAg9NSIrvBV` ("FROID Psique V2 QA"); a chave vive em `froid-server/.env` como `FROID_PSIQUE_STRIPE_TEST_SECRET_KEY` (gitignored, nunca imprimir). Metadata dos 12 objetos TEST completada (única escrita no Stripe). Rotas atrás de `FROID_PSIQUE_V2_BILLING_ENABLED=false`. Pendente: homologação manual com cartões de teste + `stripe listen` (CLI não instalado), aprovação do Fábio, e a Fase 2C só com nova autorização.

**Why:** o gate por fase é contratual (checklist em `docs/psique-v2-checklist-execucao.md`), e avançar sem aprovação repetiria o padrão que o checklist existe para impedir. O NR-1 está explicitamente fora do escopo Psique por ordem do Fábio de 29/09/2026.

**How to apply:** para revalidar os testes 2A, o DSN do PostgreSQL descartável é credencial local de cada sessão — não sondar cluster órfão de sessão anterior (o classificador bloqueia, com razão); criar cluster novo: `initdb -U psique_test -A trust`, papel `froid_runtime` NOSUPERUSER NOBYPASSRLS criado **fora** de transação com outros comandos, banco-âncora com prefixo obrigatório `psique_v2_test_`, e exportar `FROID_PSIQUE_TEST_DATABASE_URL`. Venv com pytest/ruff/mypy em `.codex-tmp/psique-v2-venv`; binários em `.codex-tmp/psique-postgres16`. Mypy dos módulos 2A: usar `--follow-imports=silent`, senão acusa o erro preexistente de `tenant_access.py:158`, que não pertence à entrega. Encerrar o servidor ao final e confirmar com `pg_ctl status`.
