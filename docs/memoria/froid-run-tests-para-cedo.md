---
name: froid-run-tests-para-cedo
description: run-tests.sh aborta na primeira suite que falha e a saida parcial parece completa
metadata: 
  node_type: memory
  type: project
  originSessionId: 39e33295-4c82-4a19-9fea-0d3df660320b
  modified: 2026-09-11T16:43:37.217Z
---

`froid-server/run-tests.sh` usa `set -euo pipefail` e captura cada suite em
`result="$(... )"`. Quando uma suite falha, a substituicao de comando devolve
codigo diferente de zero e o `set -e` **aborta o laco ali**. A saida fica com as
suites que ja passaram, sem nenhuma linha `FAIL` e sem a linha final
"Todas as suites passaram." — parece uma execucao completa e bem-sucedida.

Em 06/09/2026 isso me fez quase relatar "24 suites, todas OK" sobre um
repositorio de **104 suites**. A suite que abortava era
`test_estado_sobrevive_reconexao`, que falha no import.

**COMO RODAR A SUITE INTEIRA (apurado em 11/09/2026).** Existe um interpretador
com todas as dependencias:

```bash
cd froid-server
./.venv-win/Scripts/python.exe -m pytest tests/ -q
```

Isso roda tudo de uma vez: ~1540 testes e ~5500 subtests, em 2 minutos. Nao e
preciso laco por suite nem `run-tests.sh`.

**CORRECAO do que esta anotacao dizia antes.** Ela afirmava que `fastapi` e
`cryptography` nao estao instalados neste Windows e que o `venv/` versionado e
de Linux. A segunda parte continua verdadeira — `venv/` tem `bin/` e `lib64/` e
nao serve aqui. A primeira estava errada por falta de apuracao: **`.venv-win/`
tem cryptography, numpy e fastapi**. O `python` do PATH nao tem, e foi dele que
a conclusao saiu.

O sintoma de usar o interpretador errado e uma interrupcao na COLETA, nao uma
falha de teste:

```
ERROR tests/test_estado_sobrevive_reconexao.py
ERROR tests/test_phase4_security.py
!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!
```

O pytest para tudo e nao roda nem as suites que passariam. Antes de concluir
qualquer coisa sobre "dependencia faltando", testar os interpretadores:

```bash
for p in .venv-win/Scripts/python.exe venv/Scripts/python.exe ../.venv/Scripts/python.exe; do
  [ -f "$p" ] && echo "--- $p" && "$p" -c "import cryptography,numpy,fastapi;print('OK')" 2>&1 | tail -1
done
```

Ver [[froid-sessoes-simultaneas]] antes de qualquer `git reset --hard`.
