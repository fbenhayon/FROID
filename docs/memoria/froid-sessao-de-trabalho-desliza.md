---
name: froid-sessao-de-trabalho-desliza
description: "O login do profissional vencia 8h depois do login, em uso ou nao, e derrubava a apuracao no meio da consulta"
metadata: 
  node_type: memory
  type: project
  originSessionId: a6f7e43d-9b78-4049-8125-34e99863fa47
  modified: 2026-09-20T23:11:32.522Z
---

Em 20/09/2026, num atendimento real: chamada perfeita, paciente falando, e as
medicoes pararam. Ao encerrar, "nao autenticado" e recusa de arquivar o
relatorio. Antes disso, a faixa "esta sessao pertence a outra conta" — que era
falsa e mandava conferir a coisa errada.

**A causa.** `_session_expires_at` era escrito uma vez so, em `_issue_session`,
e NADA o renovava. A sessao de trabalho morria
`FROID_SESSION_TOKEN_TTL_SECONDS` (8h por padrao, definido no
`docker-compose.yml`) depois do LOGIN, estivesse em uso ou nao. Corrigido no
commit `082f478c`: a janela passou a contar do ultimo uso.

**O que foi descartado, e como.** Reinicio do backend apaga todos os tokens
(ver [[froid-deploy-topologia]]), e era a minha hipotese principal. Foi
falsificada por `docker inspect -f '{{.State.StartedAt}} {{.RestartCount}}'
froid-project-froid-backend-1`: de pe desde a vespera, zero reinicios. **Eu
tinha escrito a hipotese como se fosse conclusao antes de ter como conferir** —
o comando existia e custava um minuto.

**Para diagnosticar recusa de WebSocket em producao**, o backend grava auditoria
de cada conexao negada:

```bash
docker compose logs -t --since 24h froid-backend | grep websocket_audit | grep -v '"close_code":0'
```

Desde 20/09/2026 cada recusa grava o proprio `close_code` (commit `b5ad167e`), entao
o motivo sai na propria linha: 4401 login vencido, 4404 sessao de outra conta, 4402
sem saldo, 1013 acesso profissional indisponivel, 1008 papel invalido, 4403 convite
do paciente. Antes disso as seis causas produziam a mesma linha e o unico sinal era
indireto — `organization_id` preenchido significava recorte por organizacao, porque
so aquele ramo passava contexto ao auditor. Deduzir isso custou a investigacao
inteira, com paciente esperando.

A divergencia de organizacao deixou de ser recusa e virou `"outcome":"organization_mismatch"`
(ver [[froid-organizacao-ativa-vs-autoria]]) — ela aparece nesse mesmo grep.

**Fica em aberto, decisao do dono:** nao ha teto absoluto de renovacao. Uma
sessao em uso continuo nunca expira. Escolher o numero de um teto pede dado que
ninguem tem hoje.

Ver [[froid-sinal-sem-leitor]]: o canal de analise (`/ws/fusion`) era recusado e
reconectava em laco sem nada na tela, o que fez esta causa levar horas para
aparecer.
