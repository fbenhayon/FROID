#!/usr/bin/env bash
# Define (ou troca) a senha da pagina das 10 habilidades do FROID Psique
# (psique/percepcao-clinica.html). Pedido do dono, 10/11/2026.
#
# RODA NO CONSOLE DO SERVIDOR (depois de `ssh froid`, prompt root@...):
#     bash /root/froid-project/ops/definir-senha-percepcao.sh
#
# A senha e digitada aqui e nao aparece na tela, no historico do shell nem
# na lista de processos. Ao servidor vai so o hash (bcrypt), em base64, na
# linha FROID_PERCEPCAO_SENHA_HASH do .env. O usuario pedido pelo navegador
# e "froid".
#
# Por que tantas conferencias: com a variavel VAZIA o Caddy recusa a
# configuracao e o froid-edge nao sobe - o site inteiro cai, nao so a pagina.
# Entao nada e gravado sem que a configuracao nova tenha sido validada num
# conteiner descartavel, e o .env anterior fica guardado para voltar.
set -euo pipefail

PROJETO=/root/froid-project
SITE=https://www.froid.com.br/psique/percepcao-clinica.html
cd "$PROJETO"

ler_senha() {
  local a b
  read -r -s -p "Nova senha da pagina das 10 habilidades: " a; echo
  read -r -s -p "Repita a senha: " b; echo
  if [ -z "$a" ]; then echo "Senha vazia. Nada foi alterado." >&2; exit 1; fi
  if [ "$a" != "$b" ]; then echo "As duas senhas nao conferem. Nada foi alterado." >&2; exit 1; fi
  SENHA=$a
}
ler_senha

# Hash pelo proprio Caddy do servidor; a senha entra por stdin, nao por argumento.
HASH=$(printf '%s\n' "$SENHA" | docker compose exec -T froid-edge caddy hash-password | tr -d '\r\n')
case "$HASH" in
  '$2a$'*|'$2b$'*) ;;
  *) echo "O Caddy nao devolveu um hash bcrypt. Nada foi alterado." >&2; exit 1 ;;
esac
B64=$(printf '%s' "$HASH" | base64 -w0)
if [ -z "$B64" ]; then echo "Hash vazio. Nada foi alterado." >&2; exit 1; fi

echo "Validando a configuracao do Caddy com a senha nova (conteiner descartavel)..."
if ! docker run --rm -e FROID_PERCEPCAO_SENHA_HASH="$B64" \
      -v "$PROJETO/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2-alpine \
      caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
  echo "A configuracao nao valida. Nada foi alterado." >&2; exit 1
fi

COPIA=".env.bak-$(date +%Y%m%d-%H%M%S)"
cp -p .env "$COPIA"
if grep -q '^FROID_PERCEPCAO_SENHA_HASH=' .env; then
  sed -i "s|^FROID_PERCEPCAO_SENHA_HASH=.*|FROID_PERCEPCAO_SENHA_HASH=$B64|" .env
else
  printf '\nFROID_PERCEPCAO_SENHA_HASH=%s\n' "$B64" >> .env
fi
echo ".env atualizado (copia anterior: $PROJETO/$COPIA)."

echo "Recriando o froid-edge (o site fica fora por alguns segundos)..."
docker compose up -d froid-edge
for _ in $(seq 1 30); do
  codigo=$(curl -s -o /dev/null -w '%{http_code}' "$SITE" || true)
  [ "$codigo" = 401 ] && break
  sleep 1
done

sem=$(curl -s -o /dev/null -w '%{http_code}' "$SITE" || true)
# No arquivo de configuracao do curl, aspas e barra invertida precisam de escape.
ESC=${SENHA//\\/\\\\}
ESC=${ESC//\"/\\\"}
com=$(printf 'user = "froid:%s"\n' "$ESC" | curl -s -o /dev/null -w '%{http_code}' -K - "$SITE" || true)
inicio=$(curl -s -o /dev/null -w '%{http_code}' https://www.froid.com.br/ || true)
echo "Sem senha: $sem (esperado 401) | com a senha nova: $com (esperado 200) | pagina inicial: $inicio (esperado 200)"
if [ "$sem" = 401 ] && [ "$com" = 200 ] && [ "$inicio" = 200 ]; then
  echo "Pronto. Usuario: froid. Senha: a que voce acabou de digitar."
else
  echo "ALGO NAO CONFERE. Para voltar: cp -p $COPIA .env && docker compose up -d froid-edge" >&2
  exit 1
fi
