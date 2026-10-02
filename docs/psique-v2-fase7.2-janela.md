# Fase 7.2 + mecanismo 7.3 — Roteiro da janela de produção

Escrito em 02/10/2026 e atualizado para o **bundle** (a opção mais segura): esta
janela aplica numa só passada a 7.2 (consumo de sessão no V2, migration 047,
commit `e47e64ca`) e o **mecanismo dormente** da 7.3 (backfill V1→V2, migration
048, commit `bf5466ef`), ambos já no `origin/main`. A 048 é aditiva e **não é
chamada por código nenhum em execução**, então entra junto sem segundo rebuild —
um deslog só. Nenhum comando aqui roda sozinho: você cola cada bloco, e cada
bloco diz **onde** rodar.

## O que esta janela muda (e o que NÃO muda)
- **Muda só o backend.** Todas as alterações estão em `froid-server/` (migrations
  047 e 048, `main.py`, serviços). Nada de site nem de painel: a página pública e
  o SPA ficam idênticos, sem `git pull` com efeito visível e sem rebuild de
  frontend.
- **A flag já está ligada** (`FROID_PSIQUE_V2_BILLING_ENABLED=true` desde a
  Fase 6). Assim que a 047 entrar e o backend subir, **só a clínica demo**
  (`c573d2f1-768f-555f-9d64-8565bb5df7cf`, única `credit_model='psique_v2'`)
  passa a descontar o atendimento do saldo V2. Todas as outras organizações
  seguem no consumo por-profissional V1, intocadas.
- **A 048 entra dormente.** Cria a função de backfill V1→V2 e a coluna
  `ever_purchased`, mas nenhum código em execução a chama — a conversão em massa é
  a Fase 7.4. Instalar agora só adianta o mecanismo, sem mudar comportamento.
- **Ordem obrigatória:** aplicar as migrations **antes** de subir o backend novo.
  O backend velho não chama as funções novas, então aplicar com ele ainda no ar é
  seguro (047 e 048 só acrescentam tipos/função/coluna — nada é removido).

## Pré-condição (já satisfeita)
Os commits da 7.2 (`e47e64ca`) e da 7.3 (`bf5466ef`) estão no `origin/main`.
Confirmação opcional **no seu PowerShell ou Git Bash local**, no repositório:

```
git log --oneline -8
```

Devem aparecer `e47e64ca` e `bf5466ef` na lista.

---

## Passo 1 — Entrar no servidor (Git Bash, local)

Rode **no Git Bash**, sozinho. O prompt vai mudar de local para o servidor:

```
ssh froid
```

Antes: algo como `Fabio@... MINGW64 ...$`
Depois: algo como `root@FROID:~#`

**Daqui em diante, todos os blocos são no console do servidor (já dentro do
`ssh`).** Se o prompt não for `root@...`, pare: você ainda está no local.

## Passo 2 — Árvore limpa e código novo (console do servidor)

```
cd /root/froid-project && git status --short
```

Tem que vir vazio. Então puxe o código (não muda a página pública):

```
git pull --ff-only
```

```
git log --oneline -8
```

Confirme que `e47e64ca` (7.2) e `bf5466ef` (7.3) aparecem na lista. E que as duas
migrations chegaram no disco:

```
ls froid-server/migrations/047_psique_session_consumption.sql froid-server/migrations/048_psique_v2_backfill.sql
```

## Passo 3 — Backup do banco (console do servidor)

Um comando, uma linha:

```
docker exec froid-postgres-1 sh -c 'pg_dump -U "$POSTGRES_USER" -Fc froid_homologacao' > /root/froid-backups/manual/pre-fase7.2-$(date +%Y%m%d-%H%M).dump
```

Conferir que o arquivo tem tamanho > 0:

```
ls -lh /root/froid-backups/manual/ | tail -2
```

## Passo 4 — Build da imagem do backend (console do servidor)

Não derruba nada ainda; só compila o código novo:

```
docker compose build froid-backend
```

## Passo 5 — Aplicar as migrations 047 e 048 (console do servidor)

UM comando só, numa linha (o runner explícito, com o DSN administrativo da
pilha; `--through 048` pula as 001–046 já aplicadas e roda a 047 e a 048, nesta
ordem):

```
docker compose run --rm -e FROID_MIGRATION_DATABASE_URL="$FROID_DATABASE_URL" froid-backend python tools/migrate_schema.py --apply --through 048_psique_v2_backfill --confirm-database froid_homologacao
```

Saída esperada (JSON numa linha):

```
{"action": "apply", "result": ["047_psique_session_consumption", "048_psique_v2_backfill"]}
```

Se `result` vier com só uma, ou `[]`, é porque parte já estava aplicada
(idempotente — seguir mesmo assim). Qualquer `{"status": "failed", ...}`
**interrompe a janela**: não suba o backend novo; me chame com a `error_class`.

Conferência read-only de que as funções, os tipos e a coluna entraram:

```
docker exec froid-postgres-1 psql -U "$POSTGRES_USER" -d froid_homologacao -c "SELECT proname FROM pg_proc WHERE proname IN ('psique_v2_session_charge','psique_v2_session_pending_total','psique_v2_backfill_from_v1') ORDER BY 1; SELECT column_name FROM information_schema.columns WHERE table_name='organization_wallets' AND column_name='ever_purchased';"
```

Deve listar as três funções e a coluna `ever_purchased`.

## Passo 6 — Subir o backend novo (console do servidor)

**Este é o momento da janela: desloga os profissionais logados.**

```
docker compose up -d froid-backend
```

Confere que subiu:

```
docker compose ps froid-backend
```

---

## Passo 7 — Verificação de ponta a ponta (você + console do servidor)

O caminho real de `save_session_report` não tem teste automatizado; a prova é
atender uma sessão na clínica demo e ver o crédito descer.

1. **No app**, logado na clínica demo (`c573d2f1-...`), finalize o relatório de
   **uma sessão nova**. Anote o saldo antes (deve ter 500 de cortesia + o que a
   venda real somou).

2. **No console do servidor**, confira o ledger da demo — tem que aparecer uma
   linha `SESSION_CONSUMPTION` (delta −1) da sessão recém-salva:

```
docker exec froid-postgres-1 psql -U "$POSTGRES_USER" -d froid_homologacao -c "SELECT event_type,delta,funding,idempotency_key,created_at FROM credit_ledger WHERE organization_id='c573d2f1-768f-555f-9d64-8565bb5df7cf' AND event_type IN ('SESSION_CONSUMPTION','SESSION_PENDING') ORDER BY created_at DESC LIMIT 5;"
```

3. Confira o saldo da carteira (tem que ter caído 1):

```
docker exec froid-postgres-1 psql -U "$POSTGRES_USER" -d froid_homologacao -c "SELECT balance,reserved_balance,credit_model FROM organization_wallets WHERE organization_id='c573d2f1-768f-555f-9d64-8565bb5df7cf';"
```

4. **Idempotência** (opcional): salvar o mesmo relatório de novo NÃO pode criar
   uma segunda `SESSION_CONSUMPTION` com a mesma `idempotency_key`
   (`session:<id>`). O passo 2 deve continuar com uma linha só para aquela
   sessão.

Esperado: `balance` um a menos do que antes, `credit_model='psique_v2'`, uma
`SESSION_CONSUMPTION` por sessão nova. Uma organização V1 qualquer continua
descontando como antes (nada no ledger V2 dela).

## Rollback (se preciso)
Tanto a 047 quanto a 048 só **acrescentam** (tipos de evento, funções, coluna,
CHECKs mais largos); não removem nada nem alteram dados, e a 048 é dormente (sem
chamador), então não muda comportamento. O caminho de reversão operacional da
7.2 é **desligar a rota V2 de atendimento** sem desfazer a migration: como o
roteamento exige `credit_model='psique_v2'`, reverter a clínica demo para V1
(decisão deliberada, fora desta janela) tira o atendimento do V2 sem tocar no
esquema. Restaurar o dump do Passo 3 é o último recurso. Não há `DROP` a fazer.
