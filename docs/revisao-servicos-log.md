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

---

## Rodada 2 — 31/08/2026

**Escopo:** `index` (seção `#data-froid`) e `profissionais`.

Pedido do Fábio: o Data-Froid não é só validação do IPM e do IDM — é o acervo de
problemas e soluções que se acumula entre profissionais. Esse ângulo não estava escrito.

### Defeitos encontrados e fechados

| # | Página | Defeito | Classe | Como confirmar |
|---|---|---|---|---|
| 7 | `index` | A seção do Data-Froid tratava só de validação dos índices. O acervo de prática clínica entre profissionais — o segundo ativo, e o menos óbvio — aparecia como uma oração dentro de um cartão. | Completude | Quarto cartão "O que um profissional aprende com todos os outros"; a visão nomeia as duas coisas que crescem juntas |
| 8 | `profissionais` | **Zero menções ao Data-Froid** na página que vende exatamente a quem se beneficia dele. | Completude | Seção `#data-froid` própria |
| 9 | `index`, `profissionais` | `NAV_SECOES` não conhecia `#data-froid` em nenhuma das duas. Em `index` a seção existia desde 29/08 e o menu nunca soube. | Consistência | 90 âncoras de menu, todas resolvendo |

### Tensão resolvida, e vale registrar

`profissionais#relatorios` afirma que a evolução é comparada **"sempre contra a própria
linha de base do paciente — nunca contra uma população genérica"**. Uma seção nova falando
em comparar com casos parecidos pareceria contradizê-la.

A distinção foi escrita explicitamente no cartão "O que isso não muda": o progresso entre
sessões continua medido contra a linha de base do próprio paciente, e o Data-Froid
acrescenta contexto **ao lado** dessa leitura — não entra no cálculo dela. São duas
perguntas diferentes, e misturá-las produziria comparação injusta.

### Origem das afirmações novas

Exigência da skill. As consultas descritas — "casos mais parecidos", "intervenções mais
eficazes para perfis similares" — já constam de `froid-explica.html` como prompts do
produto. O piso de coorte `k = 50` consta de `etica.html`. Nada foi inventado.

### Verificação da rodada

```
paginas: 65 | ancoras de menu: 90 | FALHAS: 0
```

### Defeitos abertos

Nenhum na lista verificável. Seguem como trabalho de escopo aberto, inalterados desde a
rodada 1: `profissionais.html` (relatórios, composição customizada e área do paciente —
bloqueado por telas não levantadas e capturas inexistentes), `seguranca.html` e
`etica.html` (ainda não lidas), e os espelhos `en/es/fr`.

---

## Rodada 3 — 31/08/2026

**Escopo:** `index` e `profissionais` — elevação do Data-Froid.

Pedido do Fábio: o Data-Froid é um dos resultados de maior impacto no tratamento da saúde
mental, porque não existe estrutura capaz de captar e organizar as questões da psique.

### A calibragem, e por que ela fortalece

O pedido literal — *"não existe no planeta nenhuma estrutura"* — é **falsificável**.
Existem registros psiquiátricos nacionais, coortes de pesquisa e bases de prontuário
eletrônico, algumas com décadas de dados. Um pesquisador ou um conselheiro derruba a frase
em segundos, e leva junto a credibilidade do resto da página.

A afirmação **específica** é verdadeira e mais forte: essas bases registram o que acontece
**em volta** da sessão — diagnóstico, prescrição, desfecho. Nenhuma captura o que se passa
**dentro** dela: o que a voz revelou, o que a face confessou, o que o clínico observou e o
que fez a respeito. Essa camada nunca foi estruturada em escala, e a razão é técnica —
exigia sinal multimodal em sessão real, sem interromper o atendimento e sem identificar
ninguém.

Escrever assim demonstra conhecimento do campo em vez de ignorá-lo, e a afirmação deixa de
ser contestável.

### O que mudou

| # | Página | Mudança |
|---|---|---|
| 10 | `index` | O bloco da visão passa a explicar **por que esse acervo não existe ainda** — o argumento que faltava para a afirmação se sustentar |
| 11 | `index` | O lead da seção nomeia o alcance: não uma ferramenta melhor, mas um tipo de conhecimento que não existia |
| 12 | `index` | O hero passa a ter caminho para `#data-froid`. Era a única seção da página sem porta de entrada no topo |
| 13 | `profissionais` | O mesmo argumento, na voz de quem atende: cada sessão acrescenta uma linha ao acervo e recebe de volta o que ele acumulou |

### Verificação da rodada

```
paginas: 65 | ancoras de menu: 90 | FALHAS: 0
```

### Defeitos abertos

Nenhum na lista verificável. Escopo aberto inalterado: `profissionais` (relatórios e área
do paciente), `seguranca` e `etica`, espelhos `en/es/fr`.
