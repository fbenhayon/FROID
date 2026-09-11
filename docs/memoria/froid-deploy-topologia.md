---
name: froid-deploy-topologia
description: O que precisa de rebuild no deploy do FROID e o que entra só com git pull — e como conferir o que esta no ar com tools/conferir-deploy.py
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f1a64e5-ce7c-44b5-9fd8-8671c70cdc0e
  modified: 2026-08-07T03:42:13.189Z
---

Topologia real de produção, apurada em 07/08/2026 lendo `docker-compose.yml` e o `Caddyfile`:

- **`froid-site` é bind mount somente-leitura.** O Caddy monta `./froid-site` em `/srv/froid-site` e serve do disco. Mudança no site institucional entra **com `git pull`, sem build e sem restart de contêiner**.
- **`froid-frontend` (o SPA em `/app/`) é imagem construída** de `./froid-dashboard`. Qualquer mudança ali exige `docker compose build froid-frontend && docker compose up -d froid-frontend`.
- **`froid-backend` só precisa de rebuild se mudar código importado pelo runtime.** Arquivo em `froid-server/tools/` é ferramenta isolada — conferir com grep antes de reconstruir, porque rebuild desnecessário arrisca derrubar sessão ativa. **Corrigido em 27/08/2026, e custou duas rodadas:** isso vale para o *runtime*, não para *rodar a ferramenta*. O Dockerfile faz `COPY . .`, então script em `tools/` que você vai executar **dentro** do contêiner só existe lá depois de `docker compose build froid-backend`. E `up -d --force-recreate` **não reconstrói** — ele recria o contêiner a partir da imagem existente, aplicando mudança de *compose* (volume, env) e nenhuma de código. A sequência de mudança em ferramenta é `build` → `up -d` → executar.
- **O contexto de build do backend é `./froid-server` e não alcança a raiz do repositório.** `docs/`, `Caddyfile` e qualquer coisa fora de `froid-server/` **não entram na imagem**. Foi assim que o indexador do FROID Explica NR-1 rodou com sucesso indexando tudo menos o texto da lei: a pasta não existia lá dentro, e ausência de pasta não é erro. Hoje `docs/normas` é montado em `/normas:ro` pelo compose.
- **Diretório é `/root/froid-project`.** Contêineres com prefixo `froid-project-` (ex.: `froid-project-froid-frontend-1`), diferentes do `froid-postgres-1` de [[froid-infra-producao]], que é de outra pilha.

**Antes de montar comando de deploy, rode `python tools/conferir-deploy.py`.** Ele pergunta ao servidor por HTTP público (sem SSH) e diz, camada a camada, o que está no ar e o que não está — rotas que o site chama, cada página servida byte a byte, e as frases do painel contra o build local.

Ele existe por causa de 11/09/2026: o formulário de Sobre & Contato estava quebrado em produção nas quatro versões de idioma, porque o site entrou com `git pull` levando a página e o backend ficou para trás sem a rota `/api/contato`. Nada acusava — sem erro de build, sem teste vermelho, sem log. O `DEPLOY_LOG.md` deveria ter respondido e estava parado em junho/2026, descrevendo `uvicorn --reload` e `npx vite`: log de implantação que envelhece não é registro incompleto, é registro que mente. Foi substituído pelo comando acima e hoje só explica a topologia e o incidente.

- **Variável de ambiente nova exige linha no `docker-compose.yml`.** O `froid-backend` recebe lista explícita em `environment:`, e não `env_file`. Pôr a variável só no `.env` do servidor não a faz chegar ao contêiner — e o sintoma é o pior possível: a chave parece ligada, nada acontece, e não há erro nenhum. Apurado em 04/09/2026 ao habilitar `FROID_DATAMART_FALA_PROFISSIONAL`. Depois de ligar qualquer chave, confirmar com `docker compose exec froid-backend printenv NOME`.

**Why:** montar deploy pela suposição já custou caro neste projeto; ler o compose leva um minuto e diz exatamente o que precisa ser reconstruído.

**How to apply:** antes de qualquer deploy, rodar `git diff --name-only <base>..HEAD | sed 's|/.*||' | sort | uniq -c` para ver quais áreas mudaram, e derivar dali o que rebuildar. Ver [[froid-deploy-hetzner]] para a parte de execução. **O push por Bash NÃO é bloqueado** — apurado em 21/08/2026, `git push origin main` correu daqui sem prompt: `.claude/settings.local.json` tem `Bash(git push *)` permitido e o remoto é HTTPS com credential manager. A anotação anterior dizia o contrário e fez uma sessão inteira parar sem tentar. O que continua bloqueado é só o SSH ao servidor: os comandos de deploy vão para o Fábio colar.
