---
name: froid-deploy-hetzner
description: Como o FROID é publicado no servidor Hetzner e o papel do Fábio no deploy
metadata: 
  node_type: memory
  type: project
  originSessionId: 942a91a1-522e-4406-ac40-da424fed82cb
---

Produção do FROID (froid.com.br) corre num servidor Hetzner em 204.168.229.32, repo em `/root/froid-project`, via docker compose (serviços: froid-edge=Caddy, froid-backend=FastAPI, froid-frontend=nginx+SPA).

**Why:** A chave SSH local (`~/.ssh/id_ed25519`, fabio@FBENA) NÃO está autorizada no servidor — o deploy é sempre feito pelo Fábio colando comandos no console Linux que eu lhe passo.

**How to apply:** Fluxo de deploy: commit+push para GitHub (fbenhayon/FROID, main) → passar ao Fábio: `cd ~/froid-project && git pull origin main`. Se mudou código do painel/backend: acrescentar `docker compose up -d --build`. Se mudou o Caddyfile: acrescentar `docker compose restart froid-edge` (é bind-mount, o compose não deteta). Site estático (froid-site/) só precisa do pull. Depois validar de cá com curl às rotas. Ver [[froid-site-architecture]].
