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

---

## Rodada 4 — 31/08/2026

**Escopo:** `index` e `profissionais` — o destravamento técnico e o repertório.

Pedido do Fábio: dizer que a estruturação em escala não era possível por falta de recursos
tecnológicos, e que o FROID oferece ao profissional recursos extras — caminhos e opções
vindos de milhares de sessões, percepção de padrões, novas possibilidades de abordagem.

### O argumento que fechou o raciocínio

A rodada 3 dizia que o acervo não existia, e por quê em termos gerais. Faltava a causa
técnica, e ela é o melhor argumento dos três:

Até pouco tempo atrás, estruturar isso em escala exigiria **gravar e centralizar** áudio e
vídeo de milhares de atendimentos — precisamente o que torna a empreitada inaceitável,
ética e juridicamente. **O bloqueio nunca foi de interesse; foi de arquitetura.** O que
mudou é o processamento não precisar mais viajar: a extração acústica roda no navegador do
profissional, o rastreamento facial roda localmente, e para a base sobe o indicador, nunca
o sinal bruto.

É essa inversão que torna escala e sigilo compatíveis pela primeira vez. Sem ela, a
ambição do Data-Froid seria a mesma que qualquer um poderia declarar — e ninguém poderia
cumprir sem violar o paciente.

### O que mudou

| # | Página | Mudança |
|---|---|---|
| 14 | `index` | A causa técnica do vazio: gravar e centralizar era o único caminho, e é inaceitável. O processamento local removeu o bloqueio |
| 15 | `index` | O cartão do acervo passa a dizer o que volta ao profissional: padrões que consultório isolado não tem massa para enxergar |
| 16 | `profissionais` | O mesmo argumento na voz de quem atende, com a ressalva "você sabe disso melhor que ninguém" |
| 17 | `profissionais` | Cartão novo — repertório, não prescrição. A decisão clínica continua inteira com o profissional; o que muda é o tamanho do repertório de onde ela sai |

### Ressalva mantida em ambas as páginas

O FROID **não decide conduta**. O acervo devolve opção posta na mesa, nunca recomendação.
É a fronteira que separa apoio à decisão de substituição do julgamento clínico, e ela
precisa aparecer no mesmo parágrafo em que se promete repertório.

### Origem das afirmações

`index.html`, painel técnico: *"FFT executada no navegador via Web Audio API (não há
dependência de DSP no backend)"* e *"Vídeo processado localmente a 30+ FPS para os 468
pontos faciais"*. O processamento local é fato declarado do produto, não promessa nova.

### Verificação da rodada

```
paginas: 65 | ancoras de menu: 90 | FALHAS: 0
```

### Defeitos abertos

Nenhum na lista verificável. Escopo aberto inalterado.

---

## Rodada 5 — 31/08/2026

**Escopo:** `index`, bloco da visão do Data-Froid — reformulação aprovada pelo Fábio.

### O que estava errado na ordem anterior

O bloco afirmava grande, justificava, e recuava — "é ambição, não estado atual" no fim.
Esse padrão soa como quem se corrige. E a frase em destaque era a única parte contestável
do conjunto, enquanto o argumento realmente forte — ninguém captura o que se passa dentro
da sessão — estava enterrado no terceiro parágrafo.

Havia ainda redundância: dois parágrafos explicavam "por que não existe", um afirmando
falta de meio técnico e o outro dizendo qual.

### A ordem nova

Constatar o vazio → explicar por que ele existia → mostrar o que caiu → declarar o que se
constrói → dizer o que rende. A ambição chega no fim, já sustentada, e por isso não precisa
de desculpa.

### Alterações do Fábio nesta rodada

1. **"engenharia" no lugar de "arquitetura"** — "O bloqueio nunca foi de vontade: era de
   engenharia."
2. A frase "o processamento deixar de precisar viajar" foi substituída. **O texto de
   substituição não veio na mensagem** — o campo ficou em branco. Escrevi *"O que mudou foi
   a engenharia permitir que o sinal seja processado onde ele nasce"*, que casa com a
   escolha do item 1. **Pendente de confirmação.**
3. **"a formação de uma base gigante de informações psíquicas globais"** no lugar de "a
   maior base de informações psíquicas do planeta". Menos superfície de ataque, mesma
   ambição. A cláusula "e a primeira construída sem que ninguém precise entregar o próprio
   paciente" foi preservada.
4. **A sinergia entra no fecho:** validação e repertório juntos produzem "o efeito que
   contraria a aritmética: aquele em que 1 + 1 = 3".

### Verificação da rodada

```
paginas: 65 | ancoras: 90 | FALHAS: 0
```

### Defeitos abertos

Um item pendente de confirmação: a frase do item 2 acima. Escopo aberto inalterado.

---

## Rodada 6 — 31/08/2026

**Escopo:** ordem das seções de `index`.

O Fábio pediu o Data-Froid como segundo item. **Já estava** — desde a rodada 2. A leitura
dele era do site publicado, ainda sem o pull.

### O achado real: peso, não ordem

| Seção | Palavras |
|---|---:|
| visão-geral | 391 |
| **data-froid** | **782** |
| o-diferencial | 124 |
| para-quem-é | 163 |
| paciente | 242 |
| transparência | 206 |

O Data-Froid tem o dobro da maior e seis vezes a menor. Cresceu assim em quatro rodadas
seguidas — cada acréscimo defensável, o conjunto desproporcional. O efeito aparece na
transição: 782 palavras de acervo e filosofia seguidas de 124 sobre o Explica.

### O que mudou

 (163 palavras) subiu para logo depois do Data-Froid. É curta, aterrissa o
leitor depois do bloco longo, e responde a pergunta que ele carrega desde o começo. O
Explica vem em seguida, com o leitor já situado. Ritmo: longo → curto → curto.

Ordem final: visão-geral · data-froid · para-quem-é · o-diferencial · paciente ·
transparência.

### Proposta pendente de decisão

O peso do Data-Froid continua desproporcional. **Não removi nada** — a decisão é do Fábio.
A saída que preserva todo o conteúdo é a convenção que o próprio site já usa: deixar visíveis
a constatação, a causa e o que se constrói, e mover o aprofundamento — o parágrafo da
engenharia e o detalhe do processamento local — para um painel *Só para Nerds*. Nada se
perde e a página recupera equilíbrio.

### Verificação

```
paginas: 65 | ancoras: 90 | FALHAS: 0
```

### Defeitos abertos

Nenhum na lista verificável. Segue pendente de decisão a proposta acima sobre o peso da
seção, e a frase do item 2 da rodada 5. Escopo aberto inalterado.

---

## Rodada 7 — 31/08/2026

**Escopo:** `index`, `ciencia`, `tecnologia` — divisão do Data-Froid por página.

Proposta do Fábio, melhor que a minha: em vez de esconder o aprofundamento num painel,
distribuir cada pedaço para a página cuja pergunta ele responde. Cada argumento passa a
morar onde o leitor já está fazendo aquela pergunta.

### A divisão

| Página | O que recebeu | Por quê |
|---|---|---|
| `tecnologia#data-froid-engenharia` | O bloqueio e o que caiu: gravar e centralizar era o único caminho e é inaceitável; o sinal passou a ser processado onde nasce | Fica **acima de `#ipm-idm`**, porque é o que autoriza os dois índices a deixarem de ser heurística |
| `ciencia#data-froid-ciencia` | O que a base permite provar — e o que ela **não** prova: volume não substitui desenho experimental, é observacional, sem controle, com viés de quem procura atendimento | É a página que separa ciência publicada de metodologia própria; o Data-Froid pertence hoje à segunda coluna |
| `index#data-froid` | A constatação, a ambição e o que rende — com ponteiros para as outras duas | Continua a porta de entrada, sem carregar o argumento inteiro |

### Redução obtida

`index#data-froid` caiu de **782 para 607 palavras** e de quatro cartões para três. Dois
diziam a mesma coisa — "O acervo" e "O retorno" ambos descreviam o que volta ao
profissional — e viraram um. O cartão de validação passou a apontar para Ciência em vez de
explicar.

### O que a divisão trouxe de novo, e não existia

A seção de Ciência obrigou a escrever o que **nenhuma das versões anteriores dizia**: que
uma base grande não é ensaio clínico. É observacional, não estabelece causalidade, não tem
grupo de controle, e carrega o viés de quem procura atendimento e de quem escolhe esta
ferramenta. O que ela oferece é evidência de convergência e hipótese qualificada — o insumo
de uma validação, não a validação.

Sem essa ressalva, a promessa de "validar o IPM e o IDM" seria maior do que o método
sustenta. A divisão por página forçou a precisão que o texto único escondia.

### Verificação da rodada

```
paginas: 65 | ancoras de menu: 92 | FALHAS: 0
```

### Defeitos abertos

Nenhum na lista verificável. A proposta do painel *Só para Nerds* foi **superada** por esta
divisão e sai da lista. Segue pendente a frase do item 2 da rodada 5.
