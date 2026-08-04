# Ativação da clínica multiprofissional — roteiro do piloto

Roteiro para ligar o pool de créditos compartilhado em **uma clínica de cada
vez**. Escrito para ser seguido na ordem, com um ponto de conferência antes do
único passo irreversível.

> **Nada disso é ativado por um deploy comum.** As flags abaixo vêm desligadas
> por padrão, e o FROID continua operando no modo legado (um saldo por
> profissional) até que sejam ligadas explicitamente.

---

## Antes de começar

- [ ] Backup do estado atual (`ops/backup.sh`).
- [ ] Uma clínica escolhida para o piloto, com CNPJ e os profissionais já
      cadastrados no FROID.
- [ ] Janela de baixo movimento — nenhuma sessão em andamento nessa clínica.

---

## 1. Subir o PostgreSQL

O serviço está atrás do perfil `multitenant`, então **não sobe** num
`docker compose up` comum — é preciso pedi-lo explicitamente:

```bash
cd ~/froid-project
docker compose --profile multitenant up -d froid-postgres
docker compose ps froid-postgres     # precisa aparecer healthy
```

O Postgres **não expõe porta ao host** por decisão de segurança: só é alcançável
de dentro da rede do compose. Por isso todos os comandos abaixo rodam via
`docker compose exec`.

## 2. Ligar a persistência dual

No `.env` (nunca no Git):

```
FROID_PERSISTENCE_MODE=dual
FROID_DATABASE_URL=postgresql://froid:SENHA@froid-postgres:5432/froid
FROID_RUNTIME_DATABASE_URL=postgresql://froid_runtime:SENHA@froid-postgres:5432/froid
```

```bash
docker compose up -d --build froid-backend
docker compose logs --tail=40 froid-backend    # sem erro de conexão
```

Neste ponto o FROID **espelha** os dados no PostgreSQL, mas o saldo que vale
ainda é o legado. Nada mudou para o usuário.

## 3. Aplicar as migrações

```bash
for f in froid-server/migrations/*.sql; do
  echo "-- $f"
  docker compose exec -T froid-postgres \
    psql -U "${FROID_POSTGRES_USER:-froid}" -d "${FROID_POSTGRES_DB:-froid}" \
    -v ON_ERROR_STOP=1 < "$f" || break
done
docker compose exec froid-postgres \
  psql -U "${FROID_POSTGRES_USER:-froid}" -d "${FROID_POSTGRES_DB:-froid}" \
  -c "SELECT count(*) FROM schema_migrations;"
```

Esperado: **11**.

## 4. Deixar o espelhamento rodar

Aguarde o backfill povoar organizações, profissionais e o aporte de abertura de
cada um. Confira com a etapa 5 — ela não escreve nada.

## 5. ⚠️ Conferência (o passo que evita prejuízo)

```bash
docker compose exec froid-backend python3 ops/clinic_activation.py \
  --cnpj 12.345.678/0001-99
```

(A `FROID_DATABASE_URL` já está no ambiente do backend em modo dual, então não
é preciso passá-la.)

A saída mostra a clínica, cada profissional, o aporte de abertura de cada um, a
soma e o saldo atual da carteira.

**Confira profissional por profissional.** Perguntas a fazer:

- Todos os profissionais da clínica aparecem? Falta alguém?
- Aparece alguém que **não** é da clínica?
- O aporte de cada um bate com o saldo que ele tinha individualmente?
- A soma faz sentido com o que a clínica comprou?

Se algo divergir, **pare aqui**. Nada foi escrito ainda, e o modo legado segue
intacto. Divergência quase sempre significa profissional com CNPJ ausente ou
diferente no cadastro.

## 6. Ativar (irreversível)

Só depois de conferir, usando exatamente o número mostrado na etapa 5:

```bash
docker compose exec froid-backend python3 ops/clinic_activation.py \
  --cnpj 12.345.678/0001-99 --activate --expect 489
```

A ativação **recusa** se o número não bater — é a trava contra migrar errado.
Rodar de novo é inerte.

A partir daqui, o pool compartilhado é a autoridade do saldo dessa clínica.

## 7. Ligar o pool e a autorização, só para essa clínica

No `.env`, listando a organização explicitamente:

```
FROID_SHARED_CREDITS_MODE=enforce
FROID_SHARED_CREDITS_ORGANIZATIONS=<organization_id da etapa 5>
FROID_TENANT_AUTHORIZATION_MODE=enforce
FROID_TENANT_ENFORCEMENT_ORGANIZATIONS=<mesmo organization_id>
```

```bash
docker compose up -d froid-backend
```

Antes de ir para `enforce`, é possível usar `observe`: o comportamento continua
o legado e o FROID apenas registra se os dois saldos divergem.

## 8. Conferir pela interface

Entre como gestor da clínica e abra **Gestão da clínica** (`/clinica`):

- [ ] Saldo disponível bate com a etapa 5.
- [ ] Todos os profissionais aparecem, com uso e pacientes coerentes.
- [ ] Uma sessão de teste debita o pool (o saldo cai 1).
- [ ] Definir e remover uma cota funciona.
- [ ] A visibilidade está em **restrita** (padrão) — só mude se a clínica pediu.

---

## Se precisar voltar atrás

Antes da etapa 6 é só desligar as flags: nada foi convertido.

Depois da etapa 6, a carteira compartilhada é a autoridade. O caminho é remover
a organização das listas de `enforce` (volta a consumir pelo saldo legado) e
**conferir manualmente** o que foi consumido no período pelo `credit_ledger`,
que registra cada débito com o profissional responsável. Por isso o piloto é uma
clínica só.

---

## Requisito operacional

Os endpoints de gestão passam por validação de assinatura. Hoje isso é inerte
(`FROID_SUBSCRIPTIONS_REQUIRED=false`). Se essa flag for ligada, a clínica
precisa de assinatura ativa registrada, senão os endpoints respondem **402**.
