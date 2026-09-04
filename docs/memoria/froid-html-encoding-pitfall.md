---
name: froid-html-encoding-pitfall
description: Edições manuais do Fábio nos HTML podem corromper UTF-8 — verificar mojibake antes de commitar
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 942a91a1-522e-4406-ac40-da424fed82cb
---

Em 2026-07-16, uma edição manual do Fábio num HTML do froid-site foi gravada pelo editor com codificação errada e corrompeu os acentos das 14 páginas (mojibake: "Frequência" → "FrequÃªncia", BOM adicionado).

**Why:** O editor usado pelo Fábio re-grava todos os ficheiros abertos com dupla codificação UTF-8; o conteúdo do site é pt-BR cheio de acentos.

**How to apply:** Sempre que o git status mostrar HTML do froid-site modificado fora das minhas edições, correr `grep -c "Ã" froid-site/*.html` antes de commitar; se houver mojibake, restaurar do git (`git checkout -- froid-site/`) e reaplicar a intenção da edição via sed/Edit. Extrair a intenção do diff antes de restaurar.
