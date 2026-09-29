---
name: froid-psique-v2-estado-execucao
description: "Psique V2 commitado até a Fase 2A em 29/09/2026; Fase 2B (Stripe TEST) exige nova autorização; e o PostgreSQL de teste se recria com credencial própria, nunca se sonda o antigo"
metadata:
  node_type: memory
  type: project
  originSessionId: 6ec3bea4-fdce-409b-b3dd-be8966cb8ab3
  modified: 2026-09-29T15:19:07.916Z
---

Em 29/09/2026, com autorização do Fábio, o Psique V2 entrou no `main` em três commits cirúrgicos: `3732d6c9` (auditoria de pré-implementação), `3d570799` (Fase 1: migrations explícitas + catálogo em rascunho) e `55462af6` (Fase 2A: trial, máquina de créditos, identidade de fonte), seguidos de `c1405a6f` (registros de sessão). A frente das derivadas ([[froid-derivadas-zeradas-decisao-adiada]]) foi preservada **sem instalar** na branch `frente-derivadas-zeradas` (`8b29de78`) — instalar = merge deliberado + janela de rebuild. Tudo foi **enviado ao origin** no mesmo dia; a árvore ficou limpa. Pendências: o `git stash drop stash@{0}` ficou para o Fábio (backup provado idêntico a `e0694150`; o classificador bloqueou o descarte por mim); produção segue intocada; a **Fase 2B (Stripe TEST) exige nova aprovação explícita**. Em 29/09/2026 o Fábio estava configurando o Stripe pessoalmente e pediu que eu aguardasse o aviso dele antes de conferir — não mexer em Stripe até lá.

**Why:** o gate por fase é contratual (checklist em `docs/psique-v2-checklist-execucao.md`), e avançar sem aprovação repetiria o padrão que o checklist existe para impedir. O NR-1 está explicitamente fora do escopo Psique por ordem do Fábio de 29/09/2026.

**How to apply:** para revalidar os testes 2A, o DSN do PostgreSQL descartável é credencial local de cada sessão — não sondar cluster órfão de sessão anterior (o classificador bloqueia, com razão); criar cluster novo: `initdb -U psique_test -A trust`, papel `froid_runtime` NOSUPERUSER NOBYPASSRLS criado **fora** de transação com outros comandos, banco-âncora com prefixo obrigatório `psique_v2_test_`, e exportar `FROID_PSIQUE_TEST_DATABASE_URL`. Venv com pytest/ruff/mypy em `.codex-tmp/psique-v2-venv`; binários em `.codex-tmp/psique-postgres16`. Mypy dos módulos 2A: usar `--follow-imports=silent`, senão acusa o erro preexistente de `tenant_access.py:158`, que não pertence à entrega. Encerrar o servidor ao final e confirmar com `pg_ctl status`.
