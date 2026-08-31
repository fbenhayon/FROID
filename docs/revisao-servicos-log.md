# Log da revisão dos descritivos de serviço

Uma linha por rodada. A rodada encerra quando a lista de defeitos zera — não por
autoavaliação. Ver `.claude/skills/revisar-servicos/SKILL.md`.

---

## Rodada 1 — 31/08/2026

**Escopo percorrido:** auditoria automática das 14 páginas de descritivo, mais leitura
integral de `empresas.html` (seções `o-retrato-legal` e `o-custo-da-omissao`),
`glossario.html`, `faq.html` e `proposta-nr1.html`.

### Defeitos encontrados e fechados

| # | Página | Defeito | Classe | Como confirmar |
|---|---|---|---|---|
| 1 | `empresas` | Disclaimer jurídico ficou no meio da seção: dizia "os enquadramentos **acima**" e passou a ter conteúdo jurídico depois dele. Introduzido pelo merge M4 de 31/08. | Fluxo | O `<p>` do disclaimer é o último elemento de `#o-custo-da-omissao` |
| 2 | `empresas` | **"Inversão prática do ônus"** e **"ausência de documentação equivale a presunção desfavorável"** — juridicamente falso. Não existe inversão automática por ausência de AEP. | **Falsidade** | Texto agora cita o art. 818, § 1º da CLT e fala em redistribuição por decisão fundamentada |
| 3 | `empresas` | Link solto como fragmento de frase: "A cronologia completa, incluindo o que outras jurisdições fizeram antes." Introduzido pelo merge M1. | Gramática | A frase agora é completa e carrega a tese documental |
| 4 | `glossario` | **Zero termos do psicossocial.** 100% clínico — IPM, MFCC, FACS. Quem chegava de uma página de NR-1 não encontrava AEP, PGR, portão nem recorte declarado. | Completude | 19 verbetes acrescentados; busca por "AEP" e "piso de anonimato" retorna resultado |
| 5 | `proposta-nr1` | Única página do escopo sem qualquer menção à ISO 45003, depois do reposicionamento. | Completude | Cabeçalho cita a ancoragem e o critério de lastro do Guia do MTE |
| 6 | `faq` | 15 perguntas, todas clínicas, sem indicar onde o leitor de conformidade encontra as dele. | Completude | Lead aponta para o Explica NR-1 e para a página do método |

### Decisão registrada

**O FAQ não recebeu perguntas de conformidade.** Acrescentá-las ali borraria os dois
produtos, e elas já existem como 57 verbetes revisados no FROID Explica NR-1. O certo era
o ponteiro, não a mistura.

### Verificação da rodada

```
paginas: 65 | ancoras de menu: 88
FALHAS: 0
```

Cobre encoding, balanceamento de tags, âncoras internas e entre páginas, páginas
referenciadas, âncoras do `NAV_SECOES`, nomes aposentados e piso de coorte.

### Defeitos abertos

Nenhum na lista verificável. Os itens abaixo **não são defeitos** — são trabalho de
escopo aberto, que depende de decisão ou de insumo do Fábio.

- **`profissionais.html`** — os relatórios do profissional, a composição customizada de
  relatório e a área do paciente ainda não estão descritos. Bloqueado por dois motivos:
  as telas nunca foram levantadas, e as capturas não existem. Ver
  `docs/comercial/escopo-divulgacao-froid-psique.md`.
- **`seguranca.html` e `etica.html`** — entraram no escopo editável na skill reescrita,
  mas ainda não foram lidos. São onde vivem as afirmações sobre criptografia, isolamento
  e k-anonimato, que é a classe mais propensa a erro.
- **Espelhos `en/es/fr`** — não têm a página do método nem a cronologia desde 1986. A
  divergência é intencional por ora; vira defeito se o material internacional passar a
  ser usado em venda.
