---
name: froid-site-afirma-o-que-o-painel-nao-faz
description: "O texto vetado do site descrevia três coisas que o painel não faz; copiar site para site propaga o erro, conferir contra o código o pega"
metadata: 
  node_type: memory
  type: project
  originSessionId: fe9bfd01-927f-4751-9304-7409c74cc8a1
  modified: 2026-09-21T18:52:11.148Z
---

Em 21/09/2026, ao escrever o percurso do Psique em `froid-site/demonstracao.html`,
montei a primeira versão a partir da prosa já publicada em `profissionais.html` e
`index.html` — texto revisado, em produção havia meses. Conferido contra
`froid-dashboard/src`, três afirmações eram falsas:

- **"Verifique câmera, microfone e conexão antes de iniciar"** — não existe tela
  de pré-checagem. A permissão é pedida direto pelo navegador ao abrir a sala, e
  o diagnóstico é reativo, durante a sessão (`AvisoDeApuracao`, `DiagnosticoAcustico`).
- **"Sem Capacidade de Apuração"** com essa grafia é a regra do dono, não uma
  string da interface. A tela escreve *"Sem capacidade de apuração atual da voz."*;
  o relatório e o PDF dizem *"não medido nesta sessão"* e *"não registrado"*.
- **"Os modos simplificado e detalhado"** — são três: Sessão Simplificada,
  Sessão Detalhada e Sessão Detalhada · Índices.

**Por quê:** texto de site é copiado de site. Cada página nova herda as
afirmações da anterior e nenhuma volta ao código, então o desvio só cresce — e
é o defeito 2.4 da skill (rótulo que promete o que não entrega), agora na voz
comercial. Ver [[froid-facs-capacidade-afirmada]] e [[froid-espelhos-de-numero]].

**Como aplicar:** antes de publicar descrição de funcionalidade, confira a
afirmação em `froid-dashboard/src` — não em outra página do site. Os números do
percurso ficaram travados em `froid-server/tests/test_percurso_do_psique.py`,
que lê `TRANSCRIPT_SUMMARY_WINDOW_MS`, `SEGUNDOS_MINIMOS_DE_CORTE` e
`baselineStart + 60` do `LiveSession.tsx` e compara com o HTML.
