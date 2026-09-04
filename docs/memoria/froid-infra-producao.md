---
name: froid-infra-producao
description: "Onde ficam a branch, o banco e os contêineres de produção do FROID — e o que eu supus errado"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f1a64e5-ce7c-44b5-9fd8-8671c70cdc0e
  modified: 2026-08-05T22:48:51.800Z
---

Realidade da produção no Hetzner, apurada em 04/08/2026 depois de eu errar três suposições seguidas:

- **Branch:** produção rodou por muito tempo em `claude/froid-credits-git-access-h8o81c`, não em `main`. Consolidei as duas no commit `4b2279b`. Confirmar em qual está antes de passar comando de deploy.
- **Banco:** é `froid_homologacao` (nome enganoso — é produção), no contêiner `froid-postgres-1`, de **outra pilha** de compose. `docker compose exec froid-postgres` a partir de `~/froid-project` não funciona; use `docker exec froid-postgres-1`. Existe também `froid_db`, com 18 tabelas e sem controle de migration — origem desconhecida.
- **Migrations rodam sozinhas.** `ensure_schema()` em tenant_store.py varre `migrations/*.sql` e aplica no primeiro login. Eu afirmei o contrário várias vezes. As 010–014 do NR-1 aplicaram limpas em Postgres 15 sem ninguém pedir.
- **Numeração colidiu:** existem duas `010` e duas `011` aplicadas, porque produção e NR-1 numeraram em paralelo. `tests/test_migration_ordering.py` impede colisão nova.
- **Não existe papel `postgres` no banco.** `psql -U postgres` falha com `role "postgres" does not exist`. Ler o usuário de dentro do contêiner: `docker exec froid-postgres-1 sh -c 'psql -U "$POSTGRES_USER" -d froid_homologacao -c "..."'`. Eu passei o comando errado duas vezes.
- **Migration aplicada ≠ funcionando.** `ensure_schema()` roda na primeira operação de *tenant*, não no start do contêiner — e endpoint público sem autenticação nunca chega lá sozinho. Além disso, tabela nova precisa de `GRANT ... TO froid_runtime` explícito: sem ele a migration aplica, aparece em `schema_migrations`, e a primeira escrita falha por permissão longe do deploy que a causou.

**Why:** Cada uma dessas suposições minhas quase virou incidente — a da branch teria apagado 59 commits vivos se o git não tivesse recusado o pull.

**How to apply:** Antes de qualquer instrução de deploy ou de banco, apurar com comando de leitura em vez de confiar em anotação. Ver [[froid-deploy-hetzner]] e [[froid-nr1-corporate-module]].
