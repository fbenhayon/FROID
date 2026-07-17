# FROID — Controle de acesso multi-organização, Fase 2

## Entregas desta fase

- contexto de organização e papéis anexado à sessão autenticada;
- cabeçalho opcional `X-FROID-Organization-ID` para selecionar a organização;
- matriz de permissões testável e independente do framework;
- RLS por atribuição de paciente e por responsável pelo relatório;
- auditor sem acesso ao conteúdo clínico;
- convite, aceite e desligamento de membros;
- revogação automática das atribuições do profissional desligado;
- proteção contra remoção do último proprietário;
- auditoria de convites, entradas, desligamentos e decisões negadas;
- relatórios novos identificados com `organizationId`.

## Modos de autorização

`FROID_TENANT_AUTHORIZATION_MODE` aceita:

- `off` (padrão): mantém integralmente as regras atuais. O contexto é anexado às
  sessões e aos novos relatórios, mas não muda decisões de acesso existentes;
- `observe`: calcula a nova política e registra `observed_denial`, sem bloquear;
- `enforce`: aplica a nova política e retorna HTTP 403. Só inicia quando
  `FROID_PERSISTENCE_MODE=dual` e exige uma allowlist explícita em
  `FROID_TENANT_ENFORCEMENT_ORGANIZATIONS`.

Nunca avance diretamente de `off` para `enforce` em produção.

## Sequência de implantação

### 1. Atualização sem mudança funcional

```bash
FROID_PERSISTENCE_MODE=legacy
FROID_TENANT_AUTHORIZATION_MODE=off
docker compose up -d --build froid-backend
curl -fsS http://127.0.0.1:8000/health
```

Confirme `tenant_authorization_mode: off` e execute login, listagem, criação e
leitura de um relatório de teste.

### 2. Aplicação da migração e backfill

Com o PostgreSQL da Fase 1 saudável:

```bash
docker compose exec froid-backend python tools/migrate_legacy_to_postgres.py
```

O executor aplica `001_multitenant_foundation.sql` e
`002_access_control.sql` e `003_runtime_role_grants.sql` em ordem antes do
backfill idempotente.

Crie um usuário PostgreSQL não proprietário com senha exclusiva, fora do
histórico do shell, e reaplique as migrações para conceder apenas os privilégios
necessários:

```sql
CREATE ROLE froid_runtime LOGIN;
\password froid_runtime
```

Configure `FROID_RUNTIME_DATABASE_URL` e valide o RLS com dois IDs de
organizações de homologação:

```bash
docker compose exec froid-backend python tools/verify_tenant_rls.py \
  --organization UUID_ORG_A \
  --membership UUID_MEMBRO_A \
  --other-organization UUID_ORG_B
```

O verificador falha se o usuário runtime for proprietário de tabelas, se a
outra organização/pacientes/relatórios forem visíveis ou se as funções de papel
não estiverem acessíveis.

### 3. Observação

```bash
FROID_PERSISTENCE_MODE=dual
FROID_TENANT_AUTHORIZATION_MODE=observe
docker compose up -d froid-backend
```

Mantenha `observe` por pelo menos sete dias. Revise diariamente:

```sql
SELECT action, outcome, metadata->>'reason' AS reason, count(*)
FROM audit_events
WHERE occurred_at >= now() - interval '24 hours'
  AND outcome IN ('denied', 'observed_denial')
GROUP BY action, outcome, metadata->>'reason'
ORDER BY count(*) DESC;
```

Toda negação observada deve ser classificada como tentativa indevida, ausência
de atribuição, contexto incorreto ou regra a ajustar. Não use dados pessoais em
logs ou tickets de correção.

### 4. Piloto com bloqueio

Antes do piloto:

- todas as contas devem ter uma organização e vínculo ativos;
- profissionais devem estar atribuídos aos pacientes corretos;
- relatórios legados devem possuir organização reconciliada;
- deve existir ao menos um proprietário ativo por organização;
- backup e restauração PostgreSQL devem ter sido testados;
- as negações inesperadas em `observe` devem estar zeradas.

Ative `enforce` primeiro para uma organização interna em janela controlada:

```bash
FROID_TENANT_AUTHORIZATION_MODE=enforce
FROID_TENANT_ENFORCEMENT_ORGANIZATIONS=UUID_ORG_PILOTO
docker compose up -d froid-backend
```

Organizações fora da allowlist permanecem automaticamente em `observe`. Uma
allowlist vazia impede a inicialização em `enforce`, evitando bloqueio global
acidental.

## Matriz resumida

| Papel | Pacientes | Relatórios | Membros | Créditos | Auditoria |
|---|---|---|---|---|---|
| Proprietário | todos | gerencia | gerencia | gerencia | lê |
| Administrador | todos | gerencia | gerencia | gerencia | lê |
| Supervisor | todos, leitura | todos, leitura | não | não | não |
| Profissional | atribuídos | atribuídos/próprios | não | não | não |
| Auditor | nenhum conteúdo clínico | nenhum | não | não | lê |

## Desligamento

O endpoint de desligamento revoga o vínculo, todas as atribuições ativas e os
convites pendentes emitidos pelo membro, em uma única transação. Ele não apaga
relatórios, consentimentos ou auditoria. O próprio usuário não pode se remover
por esse endpoint; transferência de propriedade será um fluxo explícito.

## Rollback

1. Altere imediatamente `FROID_TENANT_AUTHORIZATION_MODE=observe` ou `off`.
2. Reinicie apenas o backend.
3. Confirme `/health` e os fluxos de relatório.
4. Preserve banco e auditoria para análise; não reverta migrações nem apague
   eventos.

O rollback da autorização não desativa a escrita paralela da Fase 1. Se também
houver problema de persistência, aplique o rollback documentado na Fase 1.

## Pendências antes de liberação ampla

- interface frontend para seleção de organização e gestão de membros;
- atribuição/reatribuição de pacientes pela interface;
- auditoria de exportação e compartilhamento nos respectivos fluxos;
- teste de concorrência da carteira de créditos;
- revisão de segurança e teste de restauração no ambiente de homologação.
