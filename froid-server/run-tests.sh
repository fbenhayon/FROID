#!/usr/bin/env bash
# Executa a suite de testes do backend FROID.
#
# Rode SEMPRE a partir de froid-server/ (este script garante isso). Os testes de
# DSP importam modulos do proprio diretorio - froid_f0, froid_voice, froid_facs -
# entao executa-los da raiz do repositorio falha com "No module named 'froid_f0'",
# o que parece um defeito do codigo mas e apenas caminho de import errado.
#
#   ./run-tests.sh                 # suite completa
#   ./run-tests.sh test_f0_estimation   # um modulo
#
# Testes que exigem PostgreSQL sao PULADOS automaticamente sem
# FROID_TEST_DATABASE_URL. Para incluí-los:
#
#   export FROID_TEST_DATABASE_URL=postgresql://usuario:senha@127.0.0.1:5432/froid_test
#
# e aplique as migracoes nesse banco antes (migrations/*.sql, em ordem).
#
# Dependencias: pip install -r requirements.txt
# Interpretador: Python 3.12+ (main.py usa f-string com barra invertida, que o
# 3.11 nao parseia; a imagem de producao e python:3.12-slim).
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

if [ "$#" -gt 0 ]; then
    exec "$PYTHON" -m unittest "tests.$1" -v
fi

failed=0
for file in tests/test_*.py; do
    module="tests.$(basename "$file" .py)"
    result="$("$PYTHON" -m unittest "$module" 2>&1 | tail -1)"
    case "$result" in
        OK*) printf '  ok   %-46s %s\n' "$module" "$result" ;;
        *)   printf '  FAIL %-46s %s\n' "$module" "$result"; failed=1 ;;
    esac
done

if [ "$failed" -eq 0 ]; then
    echo "Todas as suites passaram."
else
    echo "Ha suites falhando (veja acima)." >&2
    exit 1
fi
