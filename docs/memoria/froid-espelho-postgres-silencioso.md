---
name: froid-espelho-postgres-silencioso
description: "O espelho legado→PostgreSQL falha em silêncio, e é por onde nasce toda organização do NR-1 — como diagnosticar"
metadata: 
  node_type: memory
  type: project
  originSessionId: bde88982-25f5-420f-91e1-04c9a1c0b260
  modified: 2026-08-25T00:45:41.221Z
---

Apurado em 24/08/2026, depois de o NR-1 recusar todo mundo com "permissão organizacional insuficiente" por seis dias.

**A organização no PostgreSQL nasce da sincronização, e só dela.** `_organization_for_email` (tenant_store) é a única função que cria organização, usuário e vínculo. Ela só é chamada de dentro de `sync_all`, que só é chamada por `_mirror_legacy_state_to_postgres` (main), que roda dentro de um `except Exception` que registra e segue. Isso é deliberado — a gravação legada em JSON é a autoritativa e não pode ser desfeita porque o espelho falhou.

**O efeito colateral é que qualquer erro ali vira silêncio total.** O cadastro responde 200, o contêiner fica *healthy*, a suíte passa, e o sintoma aparece três camadas adiante: sem usuário no PostgreSQL não há vínculo, sem vínculo não há papel, e sem papel toda rota do NR-1 devolve 403. Ninguém liga o 403 ao cadastro.

**How to apply — o diagnóstico de 10 segundos, antes de investigar permissão:**

```
curl -s https://www.froid.com.br/health | grep -o '"last_error":"[^"]*"\|"last_sync_at":[^,]*'
```

`last_sync_at: null` + `last_error` preenchido = **o espelho nunca rodou**. Não é problema de permissão, de papel nem de RLS; é que não há linha nenhuma. Confirmar procurando a conta logada em `users`: se ela não estiver lá, é isto.

**Why:** perdi a primeira rodada investigando papéis e mensagem de 403 — melhorei o texto do erro sem tocar na causa. O 403 estava certo: não havia mesmo permissão, porque não havia membro.

**Duas causas reais encontradas, ambas invisíveis:**
- `is_clinic` lido e nunca definido — o commit `5a5a73d` (18/08) trocou o cálculo do id da organização por um helper e removeu a linha que definia o nome, deixando a que o usava.
- `legacy_owner_email` reivindicado por organização derivada de CNPJ. Essa coluna **nunca é lida**; existe só para o índice `organizations_legacy_owner_unique`. Preenchê-la numa organização de CNPJ estoura UniqueViolation assim que a mesma pessoa tem também organização própria — o autônomo que vira clínica, ou o profissional que cadastra a empresa dele no NR-1. Efeito visível idêntico ao do NameError.

**A trava:** `tests/nomes_orfaos.py` percorre a cadeia de escopos léxicos da AST e acusa nome lido que não existe em escopo algum; `tests/test_nomes_indefinidos.py` roda sobre os seis módulos de runtime. Rodar isso antes de qualquer deploy que toque `tenant_store.py` ou `main.py` — é estático, não precisa de banco, e cobre exatamente os caminhos que nenhum teste exercita.

**Padrão a generalizar:** neste servidor, `except Exception` que só loga é a assinatura de um lugar onde o defeito pode viver semanas. Ao mexer em código alcançado por um desses, a pergunta não é "os testes passam?" e sim "se isto estourar, alguém fica sabendo?". Parente de "desenho completo, camada ausente" em [[froid-nr1-corporate-module]] e de "migration aplicada ≠ funcionando" em [[froid-infra-producao]].
