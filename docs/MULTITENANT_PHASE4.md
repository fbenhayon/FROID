# FROID — Cutover e resiliência, Fase 4

## Objetivo

A Fase 4 prepara o corte controlado da persistência legada para PostgreSQL sem
transformar o banco em fonte de verdade antes de provar isolamento, integridade
e recuperação. O modo `dual` continua sendo obrigatório durante esta etapa.

## Portão automatizado de prontidão

O endpoint `GET /ready` é separado de `GET /health`:

- em `legacy`, confirma que a fonte atual continua operacional;
- em `dual`, exige banco proprietário acessível, todas as migrações aplicadas,
  RLS nas nove tabelas tenant, conexão runtime para o mesmo banco, runtime sem
  propriedade das tabelas e acesso à função restrita de papéis;
- responde HTTP 503 quando qualquer condição falhar;
- não aplica migrações, não altera dados e não retorna dados pessoais.

Execute o mesmo portão dentro do backend antes de qualquer piloto:

```bash
docker compose exec froid-backend python tools/verify_phase4_readiness.py
```

O comando lê `FROID_DATABASE_URL` e `FROID_RUNTIME_DATABASE_URL` do ambiente e
retorna código diferente de zero se o cutover não estiver pronto.

O teste de isolamento com duas organizações permanece obrigatório:

```bash
docker compose exec froid-backend python tools/verify_tenant_rls.py \
  --organization UUID_ORG_A \
  --membership UUID_MEMBRO_A \
  --other-organization UUID_ORG_B
```

## Assinaturas PRO, PLUS e MASTER

A migração `006_subscription_entitlements.sql` mantém catálogo, assinatura por
organização e identificadores de eventos Stripe. O navegador nunca informa
preço nem libera acesso. Os cinco pacotes comerciais usam IDs Stripe definidos
por `STRIPE_PRICE_PRO_10`, `STRIPE_PRICE_PRO_25`, `STRIPE_PRICE_PLUS_50`,
`STRIPE_PRICE_PLUS_100` e `STRIPE_PRICE_MASTER_25`; o webhook exige
`STRIPE_WEBHOOK_SECRET`, valida o corpo bruto e registra cada evento uma única
vez. A recarga automática somente é autorizada após consentimento expresso e
quando o saldo total da organização chega a zero. Ative
`FROID_SUBSCRIPTIONS_REQUIRED=true` somente depois de configurar os cinco
preços, o segredo do webhook e a persistência `dual`; nesse modo, `/ready` falha
com HTTP 503 se a cobrança não estiver completamente configurada.

Cada um dos cinco IDs Stripe deve ser um preço de pagamento único com opções
multimoeda BRL, USD, EUR e CNY. Os totais oficiais cobrados são:

| Pacote | BRL | USD | EUR | CNY |
|---|---:|---:|---:|---:|
| PRO 10 | 198 | 40 | 33 | 149 |
| PRO 25 | 470 | 94 | 78 | 353 |
| PLUS 50 | 1.182 | 236 | 197 | 889 |
| PLUS 100 | 2.202 | 440 | 367 | 1.656 |
| MASTER 25 | 20 | 4 | 3 | 15 |

O backend expande `currency_options` do preço, valida moeda e total antes do
Checkout e novamente no webhook. A moeda contratada é armazenada e não pode ser
trocada pela recarga automática. O consentimento de recarga registra data e
versão dos termos aceitos; uma alteração comercial exige nova contratação.

## Chaves de criptografia obrigatórias

`/ready` só libera a aplicação quando `FROID_CLINICAL_RECORD_ENCRYPTION_KEYS`
está configurada. Se o Google Agenda estiver habilitado, também exige
`FROID_TOKEN_ENCRYPTION_KEYS`. Gere duas chaves Fernet independentes no próprio
servidor, sem imprimi-las em chats ou registrá-las no Git:

```bash
docker compose run --rm --no-deps froid-backend python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Para rotação, coloque a chave nova primeiro e mantenha a anterior depois da
vírgula durante a janela de migração. Nunca remova a chave antiga antes de
confirmar que tokens e transcrições existentes abrem com a nova configuração.

## Backup e restauração comprovada

O backup é gravado inicialmente com extensão `.partial`. Ele só recebe o nome
final depois que `pg_dump` termina, o arquivo não está vazio e
`pg_restore --list` consegue lê-lo. Um SHA-256 é gerado ao lado do arquivo.

```bash
sh ops/backup_postgres.sh
```

No Hetzner atual, os scripts usam por padrão o contêiner existente
`froid-postgres-1`. Para outro ambiente, informe somente o nome correto:

```bash
FROID_POSTGRES_CONTAINER=postgres-homologacao sh ops/backup_postgres.sh
```

Para provar que o arquivo restaura, informe o backup gerado:

```bash
sh ops/verify_postgres_restore.sh \
  backups/postgres/froid-YYYYMMDDTHHMMSSZ.dump
```

O ensaio valida o checksum, cria um banco temporário com nome controlado,
restaura com `--exit-on-error`, verifica as sete migrações e RLS nas nove
tabelas tenant e remove o banco temporário mesmo em caso de falha. O banco
`$POSTGRES_DB` em produção não é usado como destino da restauração.

## Topologia atual do Hetzner

O backend de `/root/froid-project` e o PostgreSQL de `/root/froid` pertencem a
projetos Compose diferentes. Não inicie o perfil `multitenant` no servidor
atual, pois isso criaria outro PostgreSQL. Conecte o backend à rede de dados
existente usando o override versionado:

```bash
docker compose -f docker-compose.yml \
  -f ops/docker-compose.hetzner.yml up -d --build froid-backend froid-frontend froid-edge
```

O nome padrão da rede externa é `froid_froid-network` e pode ser alterado com
`FROID_DATA_NETWORK`. As URLs `FROID_DATABASE_URL` e
`FROID_RUNTIME_DATABASE_URL` devem usar o alias `postgres` dessa rede e usuários
distintos para migração e runtime restrito.

## Estado deste incremento

Esses portões validam infraestrutura e recuperação, mas não autorizam sozinhos
o corte. Concorrência da carteira, reconciliação de dados e rollback ensaiado
ainda precisam passar antes de introduzir um modo PostgreSQL autoritativo.
