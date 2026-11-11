#!/usr/bin/env bash
# Define (ou troca) uma senha conferida pelo Caddy (froid-edge).
#
#   dev        site de desenvolvedores, www.froid.com.br/dev/  (11/11/2026)
#              variavel FROID_DEV_SENHA_HASH
#   percepcao  pagina das 10 habilidades no site publico     (10/11/2026)
#              variavel FROID_PERCEPCAO_SENHA_HASH
#
# RODA NO CONSOLE DO SERVIDOR (depois de `ssh froid`, prompt root@...):
#     bash /root/froid-project/ops/definir-senha.sh dev
#
# A senha e digitada aqui e nao aparece na tela, no historico do shell nem na
# lista de processos. Ao servidor vai so o hash (bcrypt), em base64, no .env.
# O usuario pedido pelo navegador e "froid".
#
# Por que tantas conferencias: com a variavel VAZIA o Caddy recusa a
# configuracao e o froid-edge nao sobe - o site inteiro cai. Entao nada e
# gravado sem que a configuracao nova tenha sido validada num conteiner
# descartavel, e o .env anterior fica guardado para voltar.
set -euo pipefail

PROJETO=/root/froid-project
BASE=https://www.froid.com.br
case "${1:-}" in
  dev)       VAR=FROID_DEV_SENHA_HASH;       ALVO=$BASE/dev/;                          NOME="site de desenvolvedores (/dev/)" ;;
  percepcao) VAR=FROID_PERCEPCAO_SENHA_HASH; ALVO=$BASE/psique/percepcao-clinica.html; NOME="pagina das 10 habilidades" ;;
  *) echo "Uso: bash $0 dev|percepcao" >&2; exit 2 ;;
esac
cd "$PROJETO"

read -r -s -p "Nova senha do $NOME: " SENHA; echo
read -r -s -p "Repita a senha: " DE_NOVO; echo
if [ -z "$SENHA" ]; then echo "Senha vazia. Nada foi alterado." >&2; exit 1; fi
if [ "$SENHA" != "$DE_NOVO" ]; then echo "As duas senhas nao conferem. Nada foi alterado." >&2; exit 1; fi

# Hash pelo proprio Caddy do servidor; a senha entra por stdin, nao por argumento.
HASH=$(printf '%s\n' "$SENHA" | docker compose exec -T froid-edge caddy hash-password | tr -d '\r\n')
case "$HASH" in
  '$2a$'*|'$2b$'*) ;;
  *) echo "O Caddy nao devolveu um hash bcrypt. Nada foi alterado." >&2; exit 1 ;;
esac
B64=$(printf '%s' "$HASH" | base64 -w0)
if [ -z "$B64" ]; then echo "Hash vazio. Nada foi alterado." >&2; exit 1; fi

echo "Validando a configuracao do Caddy com a senha nova (conteiner descartavel)..."
if ! docker run --rm -e "$VAR=$B64" \
      -v "$PROJETO/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2-alpine \
      caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
  echo "A configuracao nao valida. Nada foi alterado." >&2; exit 1
fi

COPIA=".env.bak-$(date +%Y%m%d-%H%M%S)"
cp -p .env "$COPIA"
if grep -q "^$VAR=" .env; then
  sed -i "s|^$VAR=.*|$VAR=$B64|" .env
else
  printf '\n%s=%s\n' "$VAR" "$B64" >> .env
fi
echo ".env atualizado (copia anterior: $PROJETO/$COPIA)."

echo "Recriando o froid-edge (o site fica fora por alguns segundos)..."
docker compose up -d froid-edge
for _ in $(seq 1 30); do
  codigo=$(curl -s -o /dev/null -w '%{http_code}' "$ALVO" || true)
  [ "$codigo" = 401 ] && break
  sleep 1
done

# No arquivo de configuracao do curl, aspas e barra invertida precisam de escape.
ESC=${SENHA//\\/\\\\}
ESC=${ESC//\"/\\\"}
sem=$(curl -s -o /dev/null -w '%{http_code}' "$ALVO" || true)
com=$(printf 'user = "froid:%s"\n' "$ESC" | curl -s -o /dev/null -w '%{http_code}' -K - "$ALVO" || true)
inicio=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/" || true)
echo "Sem senha: $sem (esperado 401) | com a senha nova: $com (esperado 200) | pagina inicial publica: $inicio (esperado 200)"
if [ "$sem" = 401 ] && [ "$com" = 200 ] && [ "$inicio" = 200 ]; then
  echo "Pronto. Usuario: froid. Senha: a que voce acabou de digitar."
else
  echo "ALGO NAO CONFERE. Para voltar: cp -p $COPIA .env && docker compose up -d froid-edge" >&2
  exit 1
fi
