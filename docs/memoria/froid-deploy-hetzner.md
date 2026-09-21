---
name: froid-deploy-hetzner
description: Como o FROID é publicado no servidor Hetzner, onde ele fica de verdade, e o papel do Fábio no deploy
metadata: 
  node_type: memory
  type: project
  originSessionId: 942a91a1-522e-4406-ac40-da424fed82cb
  modified: 2026-09-12T23:33:40.574Z
---

Produção do FROID (froid.com.br) corre num servidor Hetzner em 204.168.229.32, repo em `/root/froid-project`, via docker compose (serviços: froid-edge=Caddy, froid-backend=FastAPI, froid-frontend=nginx+SPA).

**Onde a máquina fica, e as três armadilhas que fizeram errar duas vezes.** Console Hetzner → projeto FROID → servidor **#130460833, CCX33**: cidade **Helsinque**, país **FINLÂNDIA**. Apurado em 12/09/2026, depois de os documentos jurídicos publicarem dois países errados seguidos:

- **O IP engana.** `204.168.229.32` está numa faixa alocada via ARIN, a região da América do Norte. Não combina com datacenter europeu — foi justamente esse descasamento que abriu a dúvida certa, mas quem inferir o país a partir do IP vai parar nos EUA.
- **`eu-central` não é país.** É nome interno de *network zone* da Hetzner; não diz cidade nem Estado-membro.
- **Domicílio da empresa ≠ local de processamento.** Hetzner Online GmbH é sociedade alemã; o datacenter está na Finlândia. Responder "Alemanha" parece certo e é errado — e a Resolução CD/ANPD 19/2024 pergunta pelo país de **processamento**. Foi assim que a segunda resposta errada nasceu.

Antes disso, o site publicava **"Estônia"** em oito páginas e quatro idiomas, com um teste que *exigia* a frase — corrigir reprovava a suíte. Helsinque fica do outro lado do golfo de Tallinn: é quase certamente dali que a Estônia nasceu, anos atrás, sem ninguém conferir.

**Acesso direto por SSH, conferido em 21/09/2026.** `ssh froid` chega a `root@204.168.229.32` com `~/.ssh/froid-deploy-ed25519` — chave dedicada só a este host, com `IdentitiesOnly yes` no `~/.ssh/config`. São **duas** trancas, e abrir uma só não adianta: sem a regra `Bash(ssh froid:*)` em `.claude/settings.local.json`, o classificador do modo automático barra a conexão com motivo *Production Reads*, mesmo com a chave já autorizada lá.

**O que o journal mostrou, e a conclusão que eu tirei cedo demais.** Ao abrir o acesso em 21/09/2026 o `authorized_keys` já tinha `fabio@FBENA` e `froid-diagnostico`, e eu escrevi aqui que a anotação anterior estava errada — que a chave pessoal estava autorizada havia tempos e ninguém tinha testado. **Isso não se sustenta, e a anotação anterior estava provavelmente certa quando foi escrita.** O journal não registra um único login de `fabio@FBENA`, e registra o Fábio entrando **por senha** em 20/09 14:19 e 21/09 12:54, do 201.95.200.157. Cliente que tem a chave autorizada não cai para senha: o mais provável é que ela tenha entrado no arquivo naquela mesma manhã, por outra sessão, depois das 12:54. Em 18/07 uma quarta chave (`SHA256:yUrqVWjN…`, o Fábio de outra máquina) teve root em cinco logins e já não está autorizada.

**Os logins interativos do Fábio são por SENHA, não por chave.** Apurado em 21/09/2026 — `Accepted password for root from 201.95.200.157`, as duas sessões que estavam abertas. Consequência: desligar `PasswordAuthentication` corta o caminho por onde ele de facto entra, e as sessões já abertas sobrevivem (o que esconde o problema até a próxima vez). Antes de desligar, exigir prova de login por chave a partir do terminal dele, e só então mexer. O console Hetzner é a rede de segurança: é fora de banda, não passa por SSH, e `passwd -S root` devolve `P` (senha de root válida).

**Why:** O país da hospedagem é declaração jurídica nas duas Políticas de Privacidade e no Anexo II do contrato: errar ali não é detalhe de infraestrutura.

**How to apply:** Fluxo de deploy: commit+push para GitHub (fbenhayon/FROID, main) → passar ao Fábio: `cd ~/froid-project && git pull origin main`. Se mudou código do painel/backend: acrescentar `docker compose build` dos serviços afetados e `docker compose up -d`. Se mudou o Caddyfile: acrescentar `docker compose restart froid-edge` (é bind-mount, o compose não deteta). Site estático (froid-site/) só precisa do pull. Depois validar de cá com `tools/conferir-deploy.py`. Nunca inferir o país por IP nem pelo nome da zona: a fonte é o console. Ver [[froid-deploy-topologia]] e [[froid-site-architecture]].
