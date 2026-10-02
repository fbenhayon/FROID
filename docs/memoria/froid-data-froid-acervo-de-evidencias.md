---
name: froid-data-froid-acervo-de-evidencias
description: Plano em 4 fases para o Data-FROID virar base de consulta do FROID Explica por tema; decisoes do Fabio de 02/10/2026 e o estado de cada fase
metadata:
  node_type: memory
  type: project
  originSessionId: eefdced4-ce4b-47f5-8a3e-9b4a1ec23564
  modified: 2026-10-02T20:49:48.992Z
---

Objetivo do Fabio (02/10/2026): cada corte do Data-FROID = um assunto tratado, com tema registrado, para o FROID Explica consultar por tema e aconselhar o profissional. Desenho da Fase 1 em `docs/data-froid-fase1-desenho.md`.

**Decisoes (02/10/2026):** piso de coorte "bloqueia abaixo de 7" (7 passa; antes era `<= 50`, exigia 51); tema livre mas desidentificado (nao remover o filtro, trocar); paciente entra como SINTESE da questao, nunca literal; base legal do acervo e legitimo interesse sobre dado anonimizado (`lgpd_registry.py`, operacao `datamart_anonimo`) — o Fabio disse que paciente e profissional ja consentiram, mas o acervo nao depende disso.

**Fases:** 1 = linha do tempo por fala + recorte por corte + tema desidentificado + rotulos do sistema + fim dos trechos literais em claro no relatorio (implementada 02/10, aguardando commit/deploy); 2 = ligar `FROID_DATAMART_FALA_PROFISSIONAL` e reescrever registro LGPD/politica (o registro diz "sem transcricao literal"); 3 = sintese do paciente; 4 = busca por tema no FROID Explica (piso nao protege trecho: so devolver tema com >= 7 sessoes, nunca sessao do proprio profissional, so deid `ok`).

**Pendencias que ja sei:** `tools/audit_data_froid_privacy.py` reprova qualquer texto em `professional_summary_anon` — vai acusar a Fase 2; relatorios ja gravados guardam `patientSummaryAnon` literal em claro (limpeza = operacao de producao, pedir janela); `patientResponse` do navegador ainda vence o do servidor; o `.env` de producao pode fixar `FROID_ANALYTICS_MIN_K=50` — conferir com printenv.

**How to apply:** antes de mexer no acervo, ler o desenho e o estado acima; o Fabio nao quer o termo "rede neural" na conversa (ja resolvido por ele). Ver [[froid-data-froid-corpus]] e [[froid-espelhos-de-numero]].
