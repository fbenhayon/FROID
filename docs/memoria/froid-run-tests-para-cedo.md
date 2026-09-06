---
name: froid-run-tests-para-cedo
description: run-tests.sh aborta na primeira suite que falha e a saida parcial parece completa
metadata: 
  node_type: memory
  type: project
  originSessionId: 39e33295-4c82-4a19-9fea-0d3df660320b
  modified: 2026-09-06T23:07:56.706Z
---

`froid-server/run-tests.sh` usa `set -euo pipefail` e captura cada suite em
`result="$(... )"`. Quando uma suite falha, a substituicao de comando devolve
codigo diferente de zero e o `set -e` **aborta o laco ali**. A saida fica com as
suites que ja passaram, sem nenhuma linha `FAIL` e sem a linha final
"Todas as suites passaram." — parece uma execucao completa e bem-sucedida.

Em 06/09/2026 isso me fez quase relatar "24 suites, todas OK" sobre um
repositorio de **104 suites**. A suite que abortava era
`test_estado_sobrevive_reconexao`, que falha no import.

**Como rodar de verdade:** laco proprio, tolerando falha por suite —

```bash
for f in tests/test_*.py; do
  m="tests.$(basename "$f" .py)"
  r=$(python -m unittest "$m" 2>&1 | tail -1 || true)
  case "$r" in OK*) echo "  ok   $m";; *) echo "  FAIL $m  $r";; esac
done
```

**Neste Windows faltam dependencias** que nao sao defeito do codigo:
`fastapi` e `cryptography` nao estao instalados, entao
`test_estado_sobrevive_reconexao` e `test_phase4_security` falham no import.
`numpy` e `pytest` eu instalei; o `venv/` versionado e de Linux (`bin/`,
`lib64/`) e nao serve aqui.

Ver [[froid-sessoes-simultaneas]] antes de qualquer `git reset --hard`.
