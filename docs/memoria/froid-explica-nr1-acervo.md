---
name: froid-explica-nr1-acervo
description: O FROID Explica NR-1 tem acervo próprio e isolado do clínico — como reindexar e como saber se subiu completo
metadata: 
  node_type: memory
  type: project
  originSessionId: fa4449fd-a259-4e7e-b569-32bb51c38167
  modified: 2026-08-27T19:47:57.448Z
---

Construído em 27/08/2026, na véspera da apresentação da TATICCA. Duas camadas
que se sustentam sozinhas:

- **Curada** — 48 respostas em `froid-dashboard/src/lib/nr1-explica-conteudo.ts`,
  na tela `/nr1/explica`. Não faz chamada nenhuma: funciona sem rede, sem chave
  e sem índice. É o que sustenta a reunião se algo falhar.
- **Aberta** — `POST /api/organizations/{id}/nr1/explica`, com recuperação em
  `nr1_explica.py`. Sem acervo ou sem gerador devolve `disponivel: false`, e a
  tela diz que as respostas revisadas continuam valendo. Nunca erro na tela.

**A separação do acervo clínico é por collection, não por filtro.** Filtro é
condição que alguém esquece numa consulta nova; collection separada
(`froid_nr1_knowledge`) é condição que não existe para ser esquecida — abrir a
errada devolve vazio em vez de devolver o que não devia. A rota clínica
`/api/froid-explica/query` exige aprovação profissional **e injeta resumo da
carteira de pacientes** em pergunta comparativa: reusá-la para o empregador
seria a violação silenciosa. `tests/test_nr1_explica_fronteira.py` prende as
quatro separações — rota, autorização, collection e prompt — nos dois sentidos.

**Reindexar (só quando o material mudar; o índice sobrevive a rebuild porque
`./data:/data` é montado):**

```
docker compose build froid-backend && docker compose up -d froid-backend
docker compose exec froid-backend python tools/indexar_nr1_explica.py --reset
docker compose exec froid-backend python tools/indexar_nr1_explica.py --conferir
```

**O acervo completo, conferido em 27/08/2026 — 661 trechos:** norma 372 (5
fontes), interpretação 126 (4), contrato 95 (3), nota-froid 68 (7). Se
`--conferir` mostrar número muito menor ou `!!` em alguma classe, faltou fonte.

**O contrato entra citado, nunca reescrito.** As 95 seções são renderizadas de
`legal_documents.public_legal_catalog()`, a mesma fonte da tela do contrato e do
comprovante — não é cópia, e cada trecho carrega versão e sha256. A regra 8 do
prompt manda reproduzir cláusula entre aspas e nomear a seção. **Why:** o
comprovante de aceite prova um sha256; paráfrase do fornecedor sobre as
próprias obrigações vira uma segunda versão da mesma obrigação, e é a versão
sem digital.

**Nunca entram:** `docs/normas/pareceres` (opinião da nossa assessoria sobre os
nossos contratos — não é fonte citável ao cliente), notas clínicas, e os
contratos do produto clínico. O indexador recusa por construção.

**How to apply:** o corpus é o sexto espelho dos pisos, e o único que fala
direto ao comprador. `tests/test_nr1_corpus_do_explica.py` confere a prosa
contra `nr1_compliance` — foi assim que se descobriu que a nota antiga ainda
dizia "50 respostas", três dias depois da migration 027. Ver
[[froid-nr1-corporate-module]] e [[froid-deploy-topologia]].
