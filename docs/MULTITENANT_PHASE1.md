# FROID — Migração multi-organização, Fase 1

## Objetivo e limite desta fase

Esta fase cria a fundação transacional PostgreSQL para organizações, usuários,
papéis, pacientes, atribuições, consentimentos, relatórios, carteira de créditos
e auditoria. Ela **não realiza o corte do sistema para PostgreSQL**. Os arquivos
JSON continuam sendo a fonte de verdade nos modos `legacy` e `dual`.

Modos disponíveis:

- `legacy` (padrão): somente o comportamento atual; nenhuma conexão PostgreSQL.
- `dual`: grava primeiro no JSON e, depois, espelha o estado completo de forma
  idempotente no PostgreSQL. Falha do espelho não desfaz a gravação legada.

Não existe modo `postgres` nesta fase. Isso impede um corte acidental antes da
implementação dos contextos de organização, autorização granular e validação.

## Modelo de custódia

O paciente é titular dos dados, não propriedade de um profissional ou clínica.
No modelo técnico, cada registro clínico fica sob a organização controladora ou
operadora definida no contrato. Um paciente atendido por duas organizações gera
dois registros organizacionais isolados; compartilhamento futuro deverá exigir
base legal, finalidade e trilha de auditoria próprias.

Papéis iniciais: `owner`, `administrator`, `supervisor`, `professional` e
`auditor`. Um usuário pode acumular papéis. O backfill concede `owner` e
`professional` ao responsável de cada conta legada.

## Etapa 0 — preservar o estado atual

Antes de qualquer implantação no Hetzner:

```bash
cd /caminho/real/do/FROID
mkdir -p backups/phase1-$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=$(find backups -maxdepth 1 -type d -name 'phase1-*' | sort | tail -1)
cp -a data/identity_state.json data/session_reports.json "$BACKUP_DIR"/
git status -sb > "$BACKUP_DIR/git-status.txt"
sha256sum "$BACKUP_DIR"/*.json > "$BACKUP_DIR/SHA256SUMS"
```

Não prossiga se os dois JSON não estiverem no backup ou se `sha256sum -c` não
confirmar os arquivos. Faça também o snapshot/backup externo do volume do
servidor Hetzner conforme a política operacional do FROID.

## Etapa 1 — subir PostgreSQL sem alterar o backend

Copie os valores de `froid-server/.env.multitenant.example` para o `.env` usado
pelo Compose e substitua a senha. Mantenha `FROID_PERSISTENCE_MODE=legacy`.

```bash
docker compose --profile multitenant up -d froid-postgres
docker compose ps froid-postgres
docker compose exec froid-postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

O banco está em volume nomeado e não recebe tráfego do FROID nessa etapa.

## Etapa 2 — executar o backfill idempotente

Reconstrua o backend para incluir o driver PostgreSQL, mas mantenha o serviço em
modo `legacy`:

```bash
docker compose build froid-backend
docker compose up -d froid-backend
docker compose exec froid-backend python tools/migrate_legacy_to_postgres.py
```

O comando cria o schema `001_multitenant_foundation` e imprime apenas contagens,
sem expor dados pessoais. Pode ser repetido: IDs são determinísticos e os
`upserts` evitam duplicação.

Valide as contagens sem consultar PII:

```bash
docker compose exec froid-postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
"SELECT (SELECT count(*) FROM organizations) organizations,
        (SELECT count(*) FROM patients) patients,
        (SELECT count(*) FROM session_reports) reports,
        (SELECT count(*) FROM consents) consents;"'
```

## Etapa 3 — piloto com escrita paralela

Somente depois da reconciliação, altere `FROID_PERSISTENCE_MODE=dual` e reinicie
apenas o backend:

```bash
docker compose up -d froid-backend
curl -fsS http://127.0.0.1:8000/health
```

O campo `persistence` deve mostrar `mode: dual`, `schema_ready: true` após a
primeira gravação e `last_error: null`. Inicie com uma conta interna, acompanhe
logs e reconcilie diariamente as contagens durante pelo menos sete dias.

Antes do piloto, gere o primeiro backup PostgreSQL:

```bash
docker compose exec -T froid-postgres sh -lc \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "backups/postgres/froid-$(date +%Y%m%d-%H%M%S).dump"
```

## Rollback da Fase 1

1. Defina `FROID_PERSISTENCE_MODE=legacy`.
2. Execute `docker compose up -d froid-backend`.
3. Confirme `/health` e uma leitura de relatório existente.
4. Preserve o volume PostgreSQL e os logs para investigação; não apague dados.

Como o JSON é gravado antes do espelho e continua autoritativo, esse rollback
não exige restaurar o banco. Restaure os JSON do backup apenas se houver uma
falha independente confirmada neles.

## Condições antes da Fase 2/cutover

- criar usuário de runtime que não seja dono das tabelas e validar RLS;
- propagar `organization_id` e `user_id` autenticados por requisição/transação;
- implementar matriz de autorização e testes de negação entre organizações;
- implementar entrada, suspensão e desligamento de membros;
- registrar acesso, alteração, exportação e compartilhamento na auditoria;
- reconciliar carteira/razão de créditos sob concorrência;
- definir retenção, anonimização, restauração e resposta a incidentes;
- executar teste de restauração de backup e teste de segurança independente.

Até essas condições serem cumpridas, o PostgreSQL é espelho de validação e não
autoriza comercializar gestão multiprofissional como plenamente disponível.
