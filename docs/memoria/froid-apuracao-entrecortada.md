---
name: froid-apuracao-entrecortada
description: "Incidente aberto (02/10/2026) — apuracao de voz entrecortada numa sessao real com o microfone a 80%; resolver SO depois de 7.2/7.3/7.4/7.5 e demais pendencias, por ordem do Fabio"
metadata:
  node_type: memory
  type: project
  originSessionId: 6ec3bea4-fdce-409b-b3dd-be8966cb8ab3
  modified: 2026-10-02T14:42:57.556Z
---

**Incidente, 02/10/2026 (producao atual, nada a ver com a 7.2/7.3).** Numa sessao
clinica real, a apuracao parou/ficou **entrecortada** depois de ~3 minutos. O
painel de diagnostico (a versao honesta, correta — nao e bug de reporte) mostrou:
RMS 0,03062, **-30,3 dBFS**, **quadros com voz reconhecida: 2,0%**, PCM 16000 Hz,
mesmo microfone da chamada: sim, audio sem processamento confirmado: sim. O canal
NAO caiu (frames chegando); o que parou foram os indices, porque o detector de voz
rejeitou ~98% dos quadros.

**A pista que muda a hipotese:** o Fabio confirmou **microfone a 80%** (ganho
saudavel) e a chamada ouvida com clareza. Entao o -30 dBFS + 2% de voz NAO se
explicam por "entrada baixa do lado dele". O caminho de ANALISE esta vendo um
sinal mais fraco/entrecortado do que a chamada. Minha hipotese em sessao ("entrada
baixa, aproxime do mic") foi corrigida por esse dado — NAO era nivel do lado dele.

**Suspeitas a investigar (medir, nao chutar — skill-froid-master §5):**
- limiar do VAD/detector estrito demais para fala legitima porem com energia que o
  painel le baixa;
- divergencia entre o audio da chamada (que ele ouve limpo) e o PCM alimentado a
  analise — atenuacao, AGC, ou resample fazendo a analise ver -30 dBFS enquanto a
  chamada esta forte;
- entrega de quadros entrecortada (buffer/drop) depois de ~3 min, nao um corte
  seco. Ligar com [[froid-facs-capacidade-afirmada]] e os padroes 2.2 (tolerante
  virou silencioso) e 2.12 (prazo/evento de partida) da skill.

**Plano quando chegar a vez:** abrir captura + VAD, **comparar o limiar com a
distribuicao real de RMS/quadros** de uma sessao (se registrada), e checar se o
PCM da analise bate em nivel com o audio da chamada. So entao propor ajuste
medido, atras do gate. Nada em producao sem o Fabio colar.

**Why:** o Fabio determinou a ordem — resolver este item **imediatamente depois**
de concluir 7.2, 7.3 e **todas as outras pendencias** (7.4 unificar comercio +
backfill em massa + portao V2; 7.5 remover V1 morto). E a qualidade da apuracao e
o coracao clinico do produto; entregou "insatisfatoria" nas palavras dele.

**How to apply:** nao comecar antes de fechar a unificacao V2 (ver
[[froid-psique-v2-estado-execucao]]). Ao comecar, medir primeiro; a correcao e de
nivel/entrega OU de limiar, e so o dado diz qual — nunca afrouxar o detector no
chute.
