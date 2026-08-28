# Atualização do site — levantado em 27/08/2026, executado em 28/08/2026

Este documento começou como plano. Agora registra o que foi feito e o que
continua aberto, para a próxima sessão não refazer nem presumir.

---

## Executado em 28/08/2026

### `empresas.html`

| O quê | Situação |
|---|---|
| Seção "Quando o dado não basta" — a tese do recorte declarado insuficiente | feito |
| Tabela de eficácia com os três números reais do piloto | feito |
| Seção "O ciclo inteiro, operado pela contratante" — as telas que passaram a existir | feito |
| Três blocos "Só para Nerds" — efeito, amostra, fronteira | feito |
| Seção "Cinco perguntas para fazer a qualquer fornecedor" | feito |
| Preço deixou de ser a primeira seção; link no topo | feito |
| **Correção: piso de coorte dizia 50, o correto é 15** | feito |
| Row-Level Security expandido na primeira aparição | feito |

### `froid-explica-nr1.html` — página nova

Existe por colisão de nome: há dois FROID Explica, o clínico e o de NR-1, e o
menu tinha uma entrada só, apontando para o clínico. Quem chegava pelo módulo de
conformidade caía numa página sobre pacientes e IPM/IDM.

**Não trocar o destino do menu.** Isso resolveria um lado e quebraria o outro, e
deixaria a navegação diferente conforme a página. A solução adotada é o ponteiro
mútuo: `froid-explica.html` aponta para a de NR-1 no hero e num parágrafo, e a de
NR-1 aponta de volta. `como-funciona-nr1.html` também recebeu link.

Conteúdo: as duas camadas (57 respostas revisadas · 661 trechos), os oito temas
com perguntas reais, o tema das perguntas do trabalhador, o acervo com o que
entra e o que é recusado, e um bloco "Só para Nerds" sobre o isolamento por
coleção.

---

## Continua aberto

### FROID Psique — o pedido explícito do Fábio

Relatórios do paciente e do profissional. **O estado atual dessas telas continua
não levantado.** Duas sessões seguidas foram inteiras no módulo NR-1.

A próxima sessão precisa começar por aqui: abrir `SessionReport`,
`PatientPortalPage` e `Dashboard`, ver o que existe hoje, e só então decidir o
que o site deve mostrar. Não confiar em lista nenhuma para essa parte — o padrão
deste repositório é que a peça já exista e ninguém a esteja chamando.

### Capturas de tela do painel NR-1

`empresas.html` não tem **uma única imagem** — `site-img` aparece zero vezes,
enquanto `index`, `tecnologia` e `ciencia` usam capturas. É a maior fraqueza de
apresentação que sobrou, e não se resolve sem capturas reais.

Quatro que valem, na ordem de impacto: o inventário com a linha declarada
insuficiente, a tabela de eficácia, o Explica NR-1 aberto, e a recusa do painel
clínico. Guardar em `site-assets/img/` com prefixo `nr1-`.

---

## Armadilhas confirmadas deste repositório

- **`froid-site` é bind mount**: entra com `git pull`, sem rebuild. O painel
  (`froid-dashboard`) exige `docker compose build froid-frontend`.
- **Espelhos de número são o defeito mais caro daqui.** O piso de anonimato
  mudou de 50 para 15 na migration 027 e o site continuou dizendo 50 por
  semanas, numa tabela que um auditor conferiria contra a proposta impressa.
  Antes de alterar piso, margem ou corte de censo, varrer `froid-site/*.html`,
  `docs/comercial/*.md`, `proposta-nr1.html` e `tools/simulador_nr1.py`, e rodar
  `froid-server/tests/test_nr1_espelhos_do_portao.py`.
- **Conferir a matemática contra o código, não contra a memória.** A fórmula da
  amostra está em `migrations/025`, e a do efeito em `nr1_effectiveness.py`. A
  regra real de classificação é `|d| − margem ≥ 0,20`, mais rigorosa que "o
  intervalo não pode tocar o zero", que era como o site descrevia.
- **Encoding.** Edição malfeita de HTML corrompe UTF-8, e heredoc do bash quebra
  com conteúdo grande. Editar por script Python com `io.open(..., encoding=)` e
  conferir mojibake e balanceamento depois.
- **Siglas.** Expansão na primeira aparição mais glossário ao pé, em todo texto
  novo.
- **Preço.** A tabela vigente é a original — base de R$ 1.200/mês por unidade
  mais faixas de R$ 9 / 7 / 5 / 3. Foi alterada e revertida em 27/08; não
  ressuscitar a versão intermediária.
