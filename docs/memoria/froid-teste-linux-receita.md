---
name: froid-teste-linux-receita
description: Como provar o Psique V2 contra PostgreSQL real no Linux (Docker) e as quatro armadilhas que custaram uma sessao; a paridade Windows+Linux e parte do contrato
metadata:
  node_type: memory
  type: feedback
  originSessionId: 6ec3bea4-fdce-409b-b3dd-be8966cb8ab3
  modified: 2026-10-02T13:26:42.749Z
---

A norma do programa Psique V2 e provar esquema/maquina de credito contra PostgreSQL DESCARTAVEL real em DUAS plataformas: Windows (binario portatil `.codex-tmp/psique-postgres16`, venv `.codex-tmp/psique-v2-venv`) e Linux (Docker `postgres:16`). Validar so no Windows e meia validacao.

**Receita Linux:** `postgres:16` com `POSTGRES_USER=psique_test`, `POSTGRES_DB=psique_v2_test_base` (o prefixo `psique_v2_test_` e exigido pela guarda do fixture), `POSTGRES_HOST_AUTH_METHOD=trust`; criar a role `froid_runtime` (`NOSUPERUSER NOBYPASSRLS NOLOGIN`) via `docker exec ... psql`; rodar pytest dentro de `python:3.13-slim` com `--network container:<pg>` (o banco vira 127.0.0.1 e satisfaz a guarda de host). Derrubar o container no fim.

**As quatro armadilhas (02/10/2026):** (1) mount com espaco no caminho ("FROID GITHUB V5") falha no Git Bash e `-w /app` vira `C:/Program Files/Git/app` — copiar o fonte para caminho sem espaco (scratchpad), montar com `MW=$(pwd -W)` + `MSYS_NO_PATHCONV=1`; (2) `pydantic==2.7.4` nao tem wheel para py3.13 e tenta compilar Rust (ausente) -> pip aborta -> `No module named pytest` que parece erro de teste; nao pinar o que o resolvedor escolhe; (3) copiar so `*.py`/migrations/tools/tests esquece `config/` (catalogo) -> 73 "errors" de fixture (`FileNotFoundError psique_pricing_v2.json`) que parecem regressao; as fases de site/compose ainda pedem `froid-site` e `docker-compose.yml` da raiz; (4) `... | tail` esconde a causa do erro — capturar o bloco inteiro ou `--collect-only`.

**Why:** perguntaram "voce testou no Linux?" e a resposta honesta era nao — eu so tinha rodado no Windows. E os tropeços do arnês (deps, arquivos faltando) parecem regressao e poluem o numero; so vale depois de distinguir falha de codigo de artefato de setup.

**How to apply:** rode a suite-alvo ISOLADA com as deps certas para o sinal limpo; o detalhe completo (receita Windows, incremental de migration, validar como `froid_runtime`) esta na skill-froid-master secoes 8 e 9. Ver tambem [[froid-run-tests-para-cedo]] e [[froid-psique-v2-estado-execucao]].
