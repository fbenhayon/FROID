# Aceite de convite de profissional — roteiro da janela

Escrito em 02/10/2026. Deploy da correção `f16b0e24` (mostra o convite + resolve o
e-mail divergente), já no `origin/main`. **Frontend + backend** (página de aceite
nova + endpoint GET novo); **sem migration** — não há mudança de banco. Você cola
cada bloco; cada bloco diz **onde** rodar.

## O que muda (e o que não)
- **Muda frontend e backend.** Backend ganha `GET /api/organization-invitations/{token}`
  (leitura pública, não resgata nada); painel ganha a página de aceite que mostra o
  convite e trata o e-mail divergente. **Sem migration, sem mudança de dados.**
- A **trava de e-mail** do aceite continua intocada (guarda de acesso clínico).
- Rebuild de **frontend e backend** → desloga os profissionais logados por segundos.

## Passo 1 — Entrar no servidor (Git Bash, local)
```
ssh froid
```
Prompt tem de virar `root@...`. Se não virar, pare: você ainda está no local.

## Passo 2 — Código novo (console do servidor)
```
cd /root/froid-project && git status --short
```
Tem que vir vazio. Então:
```
git pull --ff-only
```
```
git log --oneline -3
```
Confirme `f16b0e24` no topo.

## Passo 3 — Backup rápido (console do servidor)
Não há mudança de banco, mas o backup é barato e é a rede de segurança:
```
mkdir -p /root/froid-backups/manual && docker exec froid-postgres-1 sh -c 'pg_dump -U "$POSTGRES_USER" -Fc froid_homologacao' > /root/froid-backups/manual/pre-convite-$(date +%Y%m%d-%H%M).dump
```
```
ls -lh /root/froid-backups/manual/ | tail -1
```

## Passo 4 — Build das imagens (console do servidor)
Não derruba nada ainda:
```
docker compose build froid-backend froid-frontend
```
Espere `Built` nos dois, sem `ERROR`.

## Passo 5 — Subir frontend e backend (console do servidor)
**Este é o momento da janela: desloga os profissionais logados.**
```
docker compose up -d froid-backend froid-frontend
```
```
docker compose ps froid-backend froid-frontend
```
Os dois têm que ficar `Up` (backend `healthy`).

## Passo 6 — Smoke do endpoint novo (console do servidor)
O GET novo tem que responder 404 em JSON para um token inexistente (prova que a
rota existe e está no ar):
```
curl -s -w "\n%{http_code}\n" https://www.froid.com.br/api/organization-invitations/TOKEN-INEXISTENTE
```
Esperado: um corpo JSON com `"detail":"convite inválido ou expirado"` e `404` na
última linha. Se vier `404` de página (HTML do nginx) ou `405`, a rota não subiu —
me chame.

## Passo 7 — Percurso real (você)
Com um **profissional real** (nada de demo):
1. Em `/clinica`, gere o convite para o **e-mail exato** do profissional (papel
   professional) e envie o link.
2. O profissional abre o link `/entrar-clinica?token=…`. A tela agora mostra
   **"Convite para <clínica> como profissional · emitido para <e-mail>"**.
3. Se ele não estiver logado, entra (Google no e-mail convidado — 1 clique — ou
   cria conta com senha e verifica o e-mail). Se estiver logado com **outro**
   e-mail, a tela oferece **"Sair e entrar com o e-mail certo"**.
4. Logado com o e-mail convidado → **"Entrar na clínica"** → aceito.

## Rollback
Sem migration: reverter é só voltar o código (`git` para o commit anterior +
rebuild) — nada de banco a desfazer. O backup do Passo 3 é a última rede.
