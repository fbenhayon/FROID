# Registro de implantação

**Este arquivo deixou de ser um log escrito à mão em 11/09/2026.** O que
responde "o que está no ar?" agora é um comando:

```bash
python tools/conferir-deploy.py
```

Ele pergunta ao servidor, por HTTP público — não precisa de SSH — e compara as
três camadas contra o repositório: as rotas que o site chama, cada página
servida byte a byte, e as frases do painel contra o build local. Onde não
consegue apurar, ele diz que não conseguiu, em vez de assumir que está tudo bem.

## Por que o log antigo saiu

As 109 linhas anteriores registravam os patches V3 a V10, de 01 a 03 de junho de
2026, e terminavam assim:

```
Subir backend:
  cd /root/froid-project/froid-server && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Subir frontend:
  cd /root/froid-project/froid-dashboard && npx vite --host 0.0.0.0 --port 5173
Acesso:
  http://204.168.229.32:5173/#/dashboard
```

Nada disso existe mais. Hoje a plataforma roda em contêineres atrás do Caddy,
com TLS e domínio próprio; `uvicorn --reload` em produção, porta 5173 exposta e
acesso por IP em HTTP são de outra era.

O arquivo ficou três meses parado enquanto o sistema mudava. E é aí que está a
lição: **log de implantação que envelhece não é registro incompleto — é registro
que mente**, porque quem o lê conclui que aquilo está no ar. Foi exatamente o
que aconteceu em 11/09/2026: procurei aqui o que estava publicado, e o que
encontrei descrevia um servidor que não existe.

## O incidente que provocou a troca

Em 11/09/2026 o formulário de Sobre & Contato estava quebrado em produção, nas
quatro versões de idioma. A página chamava `/api/contato`, o servidor devolvia
404, e o visitante recebia *"Não foi possível enviar agora"* — a mensagem se
perdia.

A rota estava certa no código. O que faltava era o deploy, e a causa é
estrutural:

| Componente | Como sobe | Efeito |
|---|---|---|
| `froid-site` | bind mount | entra com `git pull`, imediato |
| `froid-dashboard` | imagem | exige `docker compose build froid-frontend` |
| `froid-server` | imagem | exige `docker compose build froid-backend`, **derruba sessão ativa** |

Como o site entra sozinho e o backend não, é trivial publicar uma página que
chama uma rota que ainda não existe do outro lado. Nada acusa: não há erro de
build, não há teste vermelho, não há linha de log. O visitante é que descobre.

## Como publicar

```bash
cd ~/froid-project
git pull                                    # site entra aqui

docker compose build froid-frontend         # só se o painel mudou
docker compose up -d froid-frontend

docker compose build froid-backend          # só se o backend mudou
docker compose up -d froid-backend          # derruba sessão em andamento
```

Confira antes de mexer em qual componente subir, e **confira de novo depois**:

```bash
python tools/conferir-deploy.py
```

Antes de qualquer instrução sobre banco ou branch, ver
[docs/memoria/froid-infra-producao.md](docs/memoria/froid-infra-producao.md) e
[docs/memoria/froid-deploy-topologia.md](docs/memoria/froid-deploy-topologia.md):
a produção tem particularidades que já custaram três suposições erradas.
