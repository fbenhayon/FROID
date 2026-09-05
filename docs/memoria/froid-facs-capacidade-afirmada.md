---
name: froid-facs-capacidade-afirmada
description: "O motor FACS calcula 16 AUs e seis regras; o site dizia bem mais — corrigido em froid-site, pendente em froid-dashboard"
metadata: 
  node_type: memory
  type: project
  originSessionId: 450e84e4-b0df-48d4-ae9a-baeb5c7024c4
  modified: 2026-09-05T00:04:55.266Z
---

O motor facial (`froid-server/froid_facs.py`) converte 52 blendshapes em
**16 AUs** e cruza **seis regras** de dissonância (zonas 3/6/7/8/9/12).
Não há modelagem temporal de nenhum tipo: sem onset/apex/offset, sem HMM,
sem `Conf_apex`, sem duração de AU, sem microexpressão. A captura roda a
~3 quadros por segundo (`froid-face.ts`, `opts.fps ?? 3`).

Em 04/09/2026 corrigi, em `froid-site/` nos quatro idiomas, afirmações que
não tinham origem no código: "modelagem temporal de onset, apex e offset",
"468 pontos faciais a 30+ FPS", a fórmula `M_fac` com `Conf_apex`, a linha
de base facial na calibração (a calibração é só vocal) e a composição do
IPM com velocidade de contração das AUs e canal semântico por NLP.

**Ainda pendente, em `froid-dashboard/src/pages/institutional/`**
(home.html, ciencia.html, tecnologia.html): as mesmas afirmações continuam
publicadas ali, mais "Regra do Apex", "modelo de Markov de 4 estados" e
"Apex_Confidence > 0,75". Não toquei porque outra sessão estava naquele
território.

**Why:** o dono chamou afirmação de capacidade sem origem no código de "o
defeito mais caro que este site pode conter" — e o site institucional do
painel é lido pelas mesmas pessoas que leem o froid-site.

**How to apply:** antes de escrever qualquer frase sobre o que o FROID faz
com a face, abrir `froid_facs.py` e conferir. Quatro AUs (AU9, AU17, AU20,
AU26) são calculadas e nenhuma regra as lê — ver [[froid-sinal-sem-leitor]].
Os mapas publicados em `mapas-faciais.html` já declaram essas ausências;
reaproveite o texto de lá em vez de reescrever.
