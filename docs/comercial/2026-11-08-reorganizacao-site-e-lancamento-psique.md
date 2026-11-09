# Reorganização do site e lançamento do FROID Psique nas redes — 08/11/2026

Pedido do Fábio: agrupar por assunto o conteúdo disperso do site, fazer de
`percepcao-clinica.html` a página das **10 habilidades** do FROID Psique,
explicar bem o Data-Froid, divulgar as **10 sessões gratuitas** e preparar um
roteiro para apresentar o FROID a psicólogos e psiquiatras no LinkedIn,
Instagram, Facebook e YouTube.

---

## Parte 1 — O que foi feito nesta sessão

`froid-site/percepcao-clinica.html` foi reescrita como página central do
FROID Psique (arquivo ainda **não versionado** e **não ligado ao menu**):

1. Hero com o convite ao teste e as condições lidas do servidor
   (`/api/psique/v2/pricing` → `trial.credits` e `trial.days`; hoje 10 e 14).
2. As 10 habilidades, cada uma com o que registra, o que pode revelar e o
   limite da medida, e com link para a página de aprofundamento.
3. Seção própria do Data-Froid.
4. Soberania clínica (os três cartões que já existiam).
5. Chamada final para o teste, com link para `https://www.froid.com.br/cadastro`.

Cabeçalho, menu e rodapé ficaram idênticos. Não foram tocados `empresas.html`
nem `site-assets/paginas.css`, que têm alterações de outra sessão.

### As 10 habilidades e a origem de cada uma no código

| # | Habilidade | Onde está apurada |
|---|---|---|
| 01 | Calibração individual (60 s, cortes de 10 min) | `froid_core.py`, `tecnologia.html` |
| 02 | Ritmo da fala — palavras por minuto | `froid_core.py` (`words_per_minute_10m`), `froid_metrics_engine.py` ("Palavras/min") |
| 03 | Energia vocal em 12 bandas | `froid_core.py` |
| 04 | IPM e IDM — magnitude e direção | `froid_core.py`, `profissionais.html` |
| 05 | Sub-harmônicos (5–12, 12–20, 20–40 Hz) — exploratório | `froid_core.py` (`subharmonic_energy_*`) |
| 06 | Movimentos faciais em sete famílias (AU aproximadas) | motor facial, `mapas-faciais.html` |
| 07 | Transcrição com identificação de quem fala | navegador + canal de áudio |
| 08 | Coerência e dissonância **à vista do profissional** | canais lado a lado no mesmo corte |
| 09 | Relatório da sessão e evolução | `SessionReport`, `PatientDetail` |
| 10 | FROID Explica + Data-Froid | `explica_*.py`, `data_froid_referencia.py` |

### Três ajustes de mensagem, e por quê

O que o Fábio descreveu como o grande trunfo do FROID está mantido, mas com a
formulação que o produto sustenta hoje. Publicar o contrário seria anunciar uma
capacidade que o próprio site nega em outras páginas, e o público-alvo — psicólogos
e psiquiatras — é exatamente quem vai conferir.

| O que se queria dizer | O que o produto e o site dizem hoje | Formulação adotada |
|---|---|---|
| "O FROID detecta dissonância entre fala e rosto" | `etica.html`, `faq.html`, `profissionais.html`, `mapas-faciais.html`: "dissonância facial-vocal sem capacidade de apuração" | O FROID mostra voz, ritmo, rosto e conteúdo **lado a lado no mesmo corte**; o profissional percebe a coerência ou a dissonância e decide se leva ao paciente |
| "Detecta microexpressões" | Captura a ~3 quadros/s; "não oferece detecção certificada de microexpressões" | "Movimentos faciais em sete famílias", com o limite declarado |
| "Data-Froid com centenas de milhares de sessões de vários países" | `data-froid.html`: "Não divulgamos volume de sessões, cobertura mundial ou resultado clínico que não esteja documentado" | Sem número. "O acervo cresce a cada sessão elegível" |
| "A ferramenta mais sofisticada do universo", "dados irrefutáveis", "elite" | Afirmações sem como comprovar | Removidas |

Se o volume do Data-Froid existir e estiver documentado, ele entra — mas com a
fonte, e o número precisa ter um espelho testado como os demais (skill mestre,
§2.7).

---

## Parte 2 — Nova organização do site por assunto

### O problema

São 23 páginas em português. O conteúdo do FROID Psique está espalhado em dois
menus ("FROID Psique" e "Ciência e Tecnologia"), e não existe uma página que
responda, em um lugar só, à pergunta do profissional: **"o que essa ferramenta
faz por mim?"**. Essa página agora existe, mas ninguém chega até ela.

### Proposta: três portas, cada uma com um assunto

```
FROID Psique (profissionais de saúde mental)
├── As 10 habilidades ............ percepcao-clinica.html   ← porta de entrada
├── Como funciona uma sessão ..... como-funciona-clinico.html
├── Relatório e prática .......... profissionais.html
├── Data-Froid e FROID Explica ... data-froid.html, froid-explica.html
├── Ciência por trás ............. tecnologia.html, mapas-faciais.html, ciencia.html, glossario.html
├── Ética, segurança e privacidade etica.html, seguranca.html
└── Preços e teste gratuito ...... precos-psique.html, faq.html

FROID para empresas (riscos psicossociais / NR-1)
├── Visão geral .................. empresas.html
├── Cadeia de comando ............ contratacao-nr1.html
├── NR-1, ISO 45001 e 45003 ...... iso-45001.html
├── Apresentação e proposta ...... apresentacao-nr1.html, proposta-nr1.html
└── Preços ....................... precos-nr1.html

Institucional
└── Sobre e contato · Mapa do site · Privacidade · Termos
```

O que muda na prática:

1. **"Ciência e Tecnologia" deixa de ser um menu próprio.** Tudo nele explica o
   FROID Psique; passa a ser uma coluna dentro do menu do Psique.
2. **"As 10 habilidades" vira o primeiro item do menu do Psique** e o destino
   do botão principal de `index.html`.
3. **Cada página de aprofundamento ganha um link de volta** para a habilidade
   correspondente ("← As 10 habilidades").
4. **Todo link de redes sociais aponta para `percepcao-clinica.html`**, nunca
   para a home, que fala de dois produtos ao mesmo tempo.

### Ordem de execução — um commit por decisão (skill mestre, §5.1)

| Passo | O quê | Decisão do Fábio |
|---|---|---|
| 1 | Aprovar o texto de `percepcao-clinica.html` | conteúdo |
| 2 | Ligar a página ao menu e ao botão da home | navegação |
| 3 | Fundir "Ciência e Tecnologia" no menu do Psique | navegação |
| 4 | Links de volta nas páginas de aprofundamento | conteúdo |
| 5 | Versões `en/`, `es/`, `fr/` da página das 10 habilidades | idiomas |
| 6 | Imagem de compartilhamento (1200×630) para LinkedIn/Facebook/WhatsApp | aparência |

Separados, cada passo pode ser revertido sem levar os outros junto.

---

## Parte 3 — Lançamento nas redes

### 3.1 Antes do primeiro post (lista de verificação)

- [ ] `percepcao-clinica.html` publicada em produção e ligada ao menu.
- [ ] Cadastro → verificação de e-mail → 10 créditos concedidos: testar de
      ponta a ponta com uma conta nova.
- [ ] **Resolver a divergência do teste gratuito** (ver "Decisões pendentes"): o `/app/` ainda
      promete 20 sessões aos primeiros 100.
- [ ] Imagem de compartilhamento (`og:image`) na página.
- [ ] Links com UTM para medir de onde vem cada cadastro, por exemplo:
      `percepcao-clinica.html?utm_source=linkedin&utm_medium=organico&utm_campaign=lancamento-psique`
- [ ] Páginas da empresa criadas e com a mesma bio em LinkedIn, Instagram,
      Facebook e YouTube.
- [ ] Uma conta de demonstração com **paciente fictício** para gravar telas.
      Nenhum dado real de paciente aparece em vídeo, print ou anúncio.
- [ ] Se for usar Pixel da Meta ou Insight Tag do LinkedIn: aviso de cookies
      e atualização de `privacidade.html` antes.

**Bio padrão (até 150 caracteres):**
> FROID Psique: voz, ritmo da fala e expressões faciais registrados na sessão.
> Você interpreta. 10 sessões grátis ↓

### 3.2 A mensagem central

**Uma frase:** O FROID registra o que a sua escuta percebe — ritmo da fala,
energia da voz, movimentos do rosto e o assunto em discussão — para você
revisitar com dados. A interpretação continua sua.

**Três provas:** (1) o paciente comparado com ele mesmo; (2) os canais lado a
lado, no mesmo corte; (3) relatório ao fim de cada sessão.

**A oferta:** 10 sessões gratuitas, válidas por 14 dias, sem cartão.

### 3.3 Frases que podem e que não podem ser usadas

| Use | Não use |
|---|---|
| "registra", "mostra", "organiza", "aponta onde olhar" | "detecta mentira", "lê a mente", "revela o que o paciente esconde" |
| "a interpretação é sua" | "diagnostica", "identifica ansiedade/depressão" |
| "canais lado a lado para você perceber coerências e dissonâncias" | "o FROID detecta dissonância" |
| "movimentos faciais em sete famílias" | "microexpressões", "emoções verdadeiras" |
| "indicadores exploratórios" (sub-harmônicos) | "biomarcador", "comprovado cientificamente" |
| "o acervo cresce a cada sessão" | "centenas de milhares de sessões" (sem fonte documentada) |
| "10 sessões gratuitas, válidas por 14 dias" | "10 sessões grátis" sem o prazo |

Motivo: anúncio de saúde com promessa que o produto não cumpre é recusado pela
Meta e pelo LinkedIn, pode configurar publicidade enganosa (CDC, art. 37), e
destrói a credibilidade justamente com o público que mais confere.

### 3.4 Peça 1 — Vídeo manifesto (90 segundos)

Formato: horizontal (YouTube, LinkedIn) e cortado em vertical (Reels). Locução
do Fábio, legenda permanente, telas reais com paciente fictício.

| Tempo | Imagem | Locução | Texto na tela |
|---|---|---|---|
| 0–6 s | Close de um profissional ouvindo, caderno no colo | "Você já percebeu um paciente acelerar a fala no exato momento em que tocou num assunto?" | `Você percebeu.` |
| 6–14 s | O caderno: uma anotação solta, "falou rápido?" | "Você percebeu. Mas na sessão seguinte, o que sobra é a lembrança." | `E depois?` |
| 14–26 s | Tela do FROID: calibração de 60 s | "O FROID Psique começa ouvindo o próprio paciente por 60 segundos. A partir daí, ele é comparado com ele mesmo, nunca com uma média." | `O paciente comparado com ele mesmo` |
| 26–44 s | Tela: palavras por minuto e 12 bandas variando | "Durante a sessão, o FROID registra o ritmo da fala, a energia da voz em doze faixas e os movimentos do rosto, organizados em sete famílias." | `Ritmo · Voz · Rosto` |
| 44–58 s | Tela: transcrição alinhada ao corte | "E tudo isso junto do que estava sendo dito. Quando o relato diz 'está tudo bem' e a voz perde energia, você vê os dois ao mesmo tempo." | `Lado a lado, no mesmo corte` |
| 58–70 s | Relatório da sessão | "No fim, um relatório com cada corte, para você revisitar e comparar com as sessões anteriores." | `Relatório ao fim de cada sessão` |
| 70–80 s | Profissional de volta, olhando o paciente | "O FROID não diagnostica e não decide. Ele mostra onde olhar. A interpretação continua sendo sua." | `A interpretação é sua.` |
| 80–90 s | Marca + endereço | "Experimente com os seus pacientes: dez sessões gratuitas, por catorze dias, sem cartão." | `10 sessões gratuitas · froid.com.br` |

### 3.5 Peça 2 — Carrossel "As 10 habilidades" (Instagram e LinkedIn)

12 lâminas, 1080×1350.

1. **Capa:** "10 coisas que o FROID registra enquanto você escuta"
2. **Calibração:** "60 segundos de referência. Depois, o paciente é comparado com ele mesmo."
3. **Ritmo da fala:** "Palavras por minuto, a cada momento. Acelerou? Desacelerou? Você vê quando."
4. **12 bandas:** "A energia da voz em 12 faixas. Como um equalizador — não como 12 emoções."
5. **IPM e IDM:** "Quanto a voz mudou, e para que lado."
6. **Sub-harmônicos:** "Frequências muito baixas da fala, registradas como indicador exploratório."
7. **Rosto:** "Movimentos faciais organizados em sete famílias de padrões."
8. **Contexto:** "Transcrição com quem falou. Cada medida junto do assunto."
9. **Lado a lado:** "Voz, ritmo, rosto e fala no mesmo corte. Coerência ou dissonância: você decide."
10. **Relatório:** "Ao final, um relatório. Sessão de hoje comparada com as anteriores."
11. **Explica + Data-Froid:** "Um assistente que consulta os registros e o acervo. Como um bibliotecário."
12. **Chamada:** "A interpretação continua sua. 10 sessões gratuitas, 14 dias, sem cartão. Link na bio."

Legenda:
> O que a sua escuta percebe, agora com registro. Arraste para conhecer as 10
> habilidades do FROID Psique. Ele não diagnostica: mostra onde olhar.
> 10 sessões gratuitas para profissionais de saúde mental — link na bio.
> #psicologia #psiquiatria #saudemental #psicologoclinico #tecnologiaemsaude

### 3.6 Peça 3 — Série de 10 vídeos curtos (Reels, Shorts, TikTok)

Um por habilidade, 30–45 s, vertical, publicados em sequência (um a cada 2–3
dias). Estrutura fixa:

1. **Gancho (0–3 s):** uma pergunta clínica.
2. **Mostra (3–25 s):** a tela do FROID registrando aquilo.
3. **Limite (25–35 s):** o que a medida não prova.
4. **Chamada (35–45 s):** "Habilidade X de 10. Teste com 10 sessões gratuitas."

Ganchos sugeridos:

| # | Gancho |
|---|---|
| 1 | "Se o seu paciente sempre fala alto, isso é sinal de alguma coisa?" |
| 2 | "Quantas palavras por minuto o seu paciente fala quando o assunto é a mãe?" |
| 3 | "A voz tem doze faixas. Nenhuma delas é uma emoção." |
| 4 | "Não basta saber que a voz mudou. Importa para que lado." |
| 5 | "Existem frequências na fala que o seu ouvido não separa." |
| 6 | "Por que o FROID não diz se um sorriso é verdadeiro." |
| 7 | "Uma medida sem o assunto não diz nada." |
| 8 | "'Está tudo bem', disse a paciente. A voz dela disse outra coisa?" |
| 9 | "O que você lembra da sessão de três semanas atrás?" |
| 10 | "E se você pudesse perguntar a um acervo inteiro de casos?" |

### 3.7 Peça 4 — Post de lançamento do fundador (LinkedIn)

> Durante anos, ouvi profissionais de saúde mental dizerem a mesma coisa:
> "eu percebi algo na voz dele naquele momento, mas não consigo voltar lá".
>
> O FROID Psique nasceu para isso. Ele registra, durante a sessão, o ritmo da
> fala, a energia da voz, os movimentos do rosto e o que estava sendo dito —
> sempre comparando o paciente com ele mesmo, a partir de uma calibração de
> 60 segundos.
>
> Ele não diagnostica. Não diz o que o paciente sente. Mostra os canais lado a
> lado, para que o profissional perceba o que já perceberia, e agora possa
> revisitar.
>
> Reunimos o que ele faz em 10 habilidades: [link com UTM]
>
> Estamos abrindo para psicólogos e psiquiatras com 10 sessões gratuitas,
> válidas por 14 dias, sem cartão. Se você atende, eu gostaria muito da sua
> opinião — inclusive das críticas.

### 3.8 Peça 5 — Abordagem direta (mensagem no LinkedIn ou Instagram)

Personalizada, no máximo 20–30 por dia por conta, só para quem tem o cargo
declarado no perfil. Nunca em massa.

**Pedido de conexão (até 300 caracteres):**
> Olá, [nome]. Sou o Fábio, do FROID, uma ferramenta de apoio à escuta clínica
> que registra ritmo da fala, voz e expressões durante a sessão. Gostaria de
> ouvir a opinião de profissionais como você. Posso te mostrar?

**Depois do aceite:**
> Obrigado por aceitar, [nome]. Em resumo: o FROID compara o paciente com ele
> mesmo e mostra voz, ritmo, rosto e fala lado a lado; a interpretação continua
> sua. As 10 habilidades estão aqui: [link]. Você pode testar com 10 sessões
> gratuitas (14 dias, sem cartão). Se preferir, faço uma demonstração de 20
> minutos.

### 3.9 Peça 6 — E-mails para quem se cadastrou

| Quando | Assunto | Conteúdo |
|---|---|---|
| Dia 0 | Sua conta FROID está pronta | Como fazer a primeira sessão; lembrete do consentimento do paciente |
| Dia 3 | Já fez a primeira sessão? | Vídeo de 2 min lendo um relatório; oferta de demonstração |
| Dia 7 | Habilidade 8: lado a lado | Como revisar uma sessão olhando os canais juntos |
| Dia 12 | Seu teste termina em 2 dias | Créditos restantes, preços, créditos comprados não expiram |

### 3.10 Calendário das primeiras 4 semanas

| Semana | LinkedIn | Instagram / Facebook | YouTube |
|---|---|---|---|
| 1 | Post do fundador + vídeo manifesto | Carrossel das 10 habilidades + manifesto em Reels | Manifesto (horizontal) |
| 2 | Habilidades 1–3 em texto curto + abordagem direta | Reels 1, 2, 3 | Shorts 1, 2, 3 |
| 3 | Habilidade 8 em artigo + depoimento de quem testou (com autorização) | Reels 4, 5, 6, 7 | Demonstração completa (8–10 min) |
| 4 | Data-Froid e FROID Explica | Reels 8, 9, 10 | Shorts 4–10 |

### 3.11 O que medir, toda semana

| Indicador | Pergunta que responde |
|---|---|
| Visitas à página das 10 habilidades, por origem (UTM) | Qual rede traz gente? |
| Cadastros concluídos | A página convence? |
| Contas que fizeram a 1ª sessão | O produto é fácil de começar? |
| Sessões usadas no teste (média de 10) | O profissional voltou? |
| Compras de créditos ao fim do teste | Ele viu valor? |

O número mais importante é o terceiro: um cadastro que nunca abre uma sessão
não conhece o produto.

---

## Decisões pendentes do Fábio

1. **Teste gratuito: 10 ou 20 sessões?** `psique_pricing.py` e a migration 037
   dizem 10 créditos por 14 dias. `main.py` mantém `FROID_TRIAL_TIERS`
   (20 para os primeiros 100, 10 para os próximos 100), e as páginas dentro do
   `/app/` ainda prometem isso. O site e todas as peças acima usam **10 por 14
   dias**. As duas promessas não podem circular ao mesmo tempo.
2. **Volume do Data-Froid.** Existe um número documentado de sessões, países e
   profissionais? Se existir, qual é a fonte? Sem ela, nenhuma peça cita volume.
3. **Nome do produto para empresas.** `escopo-divulgacao-froid-psique.md` diz
   que "FROID NR-1" foi aposentado em favor de "FROID Psicossocial" em 31/08,
   mas o menu ainda diz "FROID NR-1". Qual vale?
4. **Aprovar o texto das 10 habilidades** antes de ligar a página ao menu
   (passos 1 e 2 da Parte 2).
