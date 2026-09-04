---
name: froid-site-architecture
description: Arquitetura site estático + SPA no mesmo domínio froid.com.br e rotas canónicas
metadata: 
  node_type: memory
  type: project
  originSessionId: 942a91a1-522e-4406-ac40-da424fed82cb
---

froid.com.br serve duas aplicações via Caddy: a raiz e páginas institucionais vêm do site estático `froid-site/` (14 páginas, tema escuro, assets em `site-assets/` para não colidir com `/assets/` do SPA); o painel (SPA React com HashRouter) vive em `/app` e nas rotas preservadas `/login`, `/cadastro`, `/paciente`, `/access/*`, `/convite/*`.

URLs canónicas de acesso usadas nos links do site: profissional `https://www.froid.com.br/app/#/login`, paciente `https://www.froid.com.br/app/#/paciente`. O index estático tem um script que redireciona qualquer hash `#/...` para `/app/#/...` (refresh do painel). `/privacidade` e `/termos` são páginas estáticas com URL limpo (try_files {path}.html).

**Why:** O SPA usa HashRouter na raiz historicamente; sem estas regras, refresh do painel cairia no site institucional e os dois `/assets` colidiam.

**How to apply:** Ao editar o site, manter links de acesso no padrão `/app/#/...`; imagens de `site-assets/` têm cache de 7 dias — ao substituir uma imagem mantendo o nome, versionar o URL (ex.: `?v=2`). Ver [[froid-html-encoding-pitfall]] e [[froid-deploy-hetzner]].
