---
name: skill-froid-master
description: As regras de conduta e os padrões de defeito apurados no FROID, para escrever, revisar, auditar, higienizar ou entregar código deste e dos próximos sistemas. Use antes de mexer em qualquer caminho que produza número, texto ou decisão que alguém vá ler como verdade — e antes de montar commit, deploy ou qualquer entrega.
---

# Rigor de engenharia — o que aprendemos apanhando

Este documento não é estilo. Cada regra abaixo custou um incidente concreto, e o
caso está junto porque é ele que faz o padrão ser reconhecido da próxima vez. Um
princípio sem o caso vira frase de parede.

Vale para o FROID e para os próximos sistemas.

---

## 1. As três que não se negociam

### 1.1 Onde não há apuração, declare a ausência. Nunca preencha.

Determinação do dono, 03/09/2026, depois de uma sessão de 24 minutos analisada
inteira sobre voz simulada, cujo relatório era indistinguível de um relatório
legítimo:

> É terminantemente proibida a utilização de quaisquer simulação de informação.
> Quando não existe a capacidade de apuração, informar "Sem Capacidade de
> Apuração". Nunca jamais supor ou inventar absolutamente nada.

Reafirmada pelo dono em 08/09/2026, com um verbo a mais:

> não deve "supor, inventar ou chutar nada".

Os três não são sinônimos, e a diferença importa porque cada um falha num
lugar diferente do código:

- **supor** — preencher o que não foi apurado. O default silencioso, o
  `|| 0`, o carry-forward. É o mais fácil de achar: procure operador de
  fallback em caminho de medida.
- **inventar** — publicar como medida algo que não veio de medida nenhuma. O
  `np.random.choice` de tom que rodava sempre, inclusive com áudio real
  chegando, e os quatro campos derivados dele.
- **chutar** — escolher número sem dado que o sustente: limiar, peso, faixa,
  piso de coorte, teto de tokens. Se o dado ainda não existe, diga que não
  existe e diga qual medição o produziria (§5).

O corolário vale para os três: **não fazer nada disso não é o mesmo que
recusar-se a responder.** A saída correta é declarar a ausência com o nome que
ela tem e dizer o que faltou — "Sem Capacidade de Apuração", e não silêncio,
não meia frase, não um número modesto para não ficar vazio.

Na prática isto proíbe mais coisas do que parece:

- `_safe_float(value, default=0.0)` — ausência vira zero na gravação, e `0,00`
  num relatório é tipograficamente indistinguível de uma medida real de zero.
  Um paciente recebeu quatro páginas com vinte e uma linhas em `0,00`.
- `0.0 or -120.0` em Python devolve `-120.0` — o fundo de escala virou silêncio.
- `|| "neutro"`, `?? 0`, `.get(campo, 0)` em caminho de métrica.
- Carry-forward: último valor conhecido apresentado como valor atual.

**Índice em branco significa "não medido", nunca "zero".**

### 1.2 Não troque uma suposição por outra

Ao consertar a apresentação dos zeros, a tentação era inferir "zero significa
ausência". Errado: isso é adivinhar. A distinção voltou por **afirmação
registrada** — o campo de procedência (`voice_features_source`, `f0_source`,
`facs_source`), que diz o que de fato entrou no cálculo.

Quando não há afirmação registrada (relatório antigo), a saída honesta é
*"não registrado"* — nem afirma que mediu, nem acusa quem talvez tenha medido.

### 1.3 Falhe fechado, e diga que fechou

- Problema de infraestrutura **nunca** amplia acesso.
- Meia frase é pior que frase nenhuma: quem lê não tem como saber o que faltou.
- Mas silêncio também não serve. Toda recusa grava o **motivo**
  (`professional_deid_reason`), porque acervo vazio sem motivo é
  indistinguível de acervo que ninguém alimentou — e a diferença entre "recusei
  90% por ambiguidade" e "o pipeline não roda" só apareceria quando alguém
  fosse consultar e não achasse nada.

**Corolário (regra do dono, 04/09/2026):** preservar a substância vale mais que
recusar por precaução. O descarte deve ser o mais local possível — o período, não
a fala inteira — e todo corte precisa ser visível (`[OMITIDO]`), porque texto que
parece completo e não é engana quem consulta. Recusar tem teto: metade do
registro em buracos não ensina nada e ainda ocupa uma linha parecendo que ensina.

---

## 2. Os padrões de defeito, com o caso que os revelou

### 2.1 Desenho completo, camada ausente

**A peça existe, está correta, e nada a consome.** É o padrão mais frequente
desta casa — apareceu mais de dez vezes:

| A peça | Quem deveria consumi-la |
|---|---|
| `MAX_VISIBLE_TRANSCRIPT_LINES` | nada renderizava — o nome prometia visibilidade que nunca existiu |
| `patientViewFor`, três timestamps, canal semântico | nenhum leitor |
| sub-harmônicos medidos, `apuracao_disponivel`, `facs_source` | o painel não lia |
| `cut_summary_anon`, `patient_summary_anon`, `professional_summary_anon` | colunas no esquema, `""` no INSERT |
| `.nav-links a.ativo` (itálico + sublinhado) | **zero** páginas usavam a classe |
| `froid-explica-nr1.html` | existia, traduzido, e não estava no menu |

**Como caçar:** liste as chaves que a origem emite e verifique, uma a uma, se
alguém as **renderiza** — não basta aparecer num tipo TypeScript ou num teste.
Depois faça o inverso: constantes e colunas definidas que não decidem nada.

### 2.2 Tolerante a falhas virou silencioso

`catch { return () => {} }` na captura acústica: indistinguível de sucesso. A
sessão inteira rodou sem PCM e ninguém soube.

**Regra:** todo caminho de degradação precisa **reportar**. Se o sistema
continua funcionando sem uma peça, alguém tem de ficar sabendo que a peça faltou.

**E silêncio não é a única forma de não reportar.** Em 20/09/2026 o canal de
análise foi recusado pelo servidor e o painel seguiu exibindo o aviso calmo
montado sobre o **último tique que havia chegado**: *"o áudio do paciente está
chegando — o microfone está funcionando. Se ele estiver em silêncio, não há nada
a corrigir."* Era verdade um minuto antes, e passou a ser o contrário do que
acontecia. Um aviso alimentado por dado de chegada tem de saber quando o canal
caiu; senão deixa de reportar o presente e passa a **afirmar o passado** — o que
é pior que não dizer nada, porque quem lê age sobre ele e para de procurar.

### 2.3 A chave que não chega

`FROID_DATAMART_FALA_PROFISSIONAL=1` no `.env` do servidor não chegaria ao
contêiner: o `froid-backend` recebe **lista explícita** em `environment:`, não
`env_file`. A chave pareceria ligada, nada aconteceria, e não haveria erro nenhum.

**Regra:** variável nova exige linha no `docker-compose.yml`, e depois de ligar
qualquer chave, confirmar: `docker compose exec froid-backend printenv NOME`.

### 2.4 Rótulo que promete o que não entrega

- "Medidas a cada dez minutos" sobre cortes manuais de 3min37 e **12 segundos**.
- `MAX_VISIBLE_TRANSCRIPT_LINES` sem nada visível.
- Menu com "FROID Explica" genérico levando ao produto errado.

Título que descreve outra coisa é pior que nenhum, porque o leitor confia nele.

### 2.5 Acerto por sorte

O resumidor escreveu *"O filho, por outro lado, defende..."*. Estava certo — e o
sistema não sabe quem é filho de quem: leu do conteúdo. O **mesmo mecanismo**
trocou a cidade e produziu o trecho incoerente que um paciente apontou.

**Regra:** distinga o que é **medido** do que é **inferido**, e nomeie a fonte.
Quem falou é medida (vem do canal de áudio, rótulo fixo `DR.`/`PC`); parentesco e
papel são conteúdo (vêm do que foi dito). Um acerto por sorte continua sendo
sorte, e o próximo caso é o erro.

### 2.6 Critério que não é sobre o dado

- Empate no classificador resolvido pela **ordem da lista** — vencia o primeiro
  escrito. É um critério, mas não um critério sobre o texto. Empate não classifica.
- Média **simples** onde cabia ponderada: `146,17` contra `161,8` no mesmo
  documento, porque a simples dava ao corte de 12 segundos o mesmo peso do de
  7min47.
- Casamento por **substring** sem fronteira: `"como"` dentro de *comodidade*,
  `"corpo"` dentro de *corporativo*, `"?"` engolindo todo o balde de perguntas.
- Peso igual para indícios de força desigual: `"sistema nervoso"` é evidência
  muito mais forte que `"corpo"`.

### 2.7 Espelhos de número

O mesmo número copiado em vários lugares diverge em silêncio. Piso de coorte no
servidor, no site, no painel e no simulador de proposta comercial. Um deles
sobreviveu a uma migração com o valor antigo — e ia parar numa planilha de venda.

**Regra:** número tem **uma** fonte. Onde a cópia é inevitável (HTML estático,
outra linguagem), existe teste que compara todas contra a fonte, e o glob cobre a
próxima cópia sem ninguém precisar lembrar.

### 2.8 Corrigi o lugar, não a regra

Removi um `|| "neutro"` e declarei resolvido. Havia mais quatro no mesmo arquivo.

**Regra:** ao corrigir, o teste varre o **arquivo inteiro** (ou o repositório)
pela regra, não pela ocorrência que você viu.

---

### 2.9 Espelhos de nome — e uma busca que casa por nome

Irmã da 2.7, e mais difícil de ver: ali era o mesmo **número** copiado em
vários lugares; aqui é a mesma **coisa** chamada por nomes diferentes, com
alguém procurando por nome.

**O caso, 07/09/2026.** O FROID Explica recebeu a tabela de métricas do painel
e passou a casar cada pergunta pelo **rótulo que o profissional lê na tela**.
Só que cada tela escreve o rótulo do seu jeito:

| Sessão ao vivo | Relatório | Ficha do paciente |
|---|---|---|
| `TOM` | `Tom` | `Tom` |
| `JITTER` | `Jitter idx.` | `Jitter idx.` |
| `DELTA` | `Delta 0.5-4Hz` | — |
| `IND. ESPECTRAL` | `Ind. espectral` | `Ind. espectral` |

Mandar o dialeto local de cada tela faria a busca não encontrar nada — e o
sintoma não seria um erro: seria o assistente respondendo **"o valor não foi
enviado pelo painel"** sobre um número impresso três centímetros acima da
caixa de pergunta. Exatamente o defeito que aquele trabalho tinha ido corrigir,
de volta, agora num lugar onde ninguém procuraria.

**A saída** foi um produtor único — `lib/painel-para-o-explica.ts` — que emite
os rótulos **canônicos**, e um teste que confronta rótulo, campo de origem e
casas decimais contra a tabela que a tela ao vivo renderiza. As tabelas
visíveis de cada tela continuam exatamente como estavam: o vocabulário
compartilhado é o do **consumidor**, não o da tela.

**Regra:** onde um consumidor casa por NOME — glossário, de-para, dicionário
de tooltip, alias, chave de tradução, coluna de junção —, o nome tem **uma**
fonte, e quem publica converte para ela. Renomear na tela é livre; renomear no
contrato não.

**Como caçar:** liste os nomes que cada produtor emite e os que o consumidor
espera, e compare os dois conjuntos **por igualdade**, não por olhar. Onde a
correspondência for por semelhança de texto — normalização de acento, caixa ou
separador —, ela já é um palpite: `SUB-H` não vira `subharmonic` por
normalização nenhuma, e casar por parecido erra em silêncio e aponta a métrica
errada. Prefira a tabela explícita, e faça a falta de correspondência **aparecer**
(no FROID a métrica sem régua sai declarada "sem faixa avaliável", nunca pintada
como se estivesse dentro dela).

---

### 2.10 A guarda que só alcança quem ela deveria proteger

**O caso, 20/09/2026, com o paciente já na sala.** O profissional foi barrado da
própria consulta, onze vezes. A rota do WebSocket perguntava, nesta ordem:

1. o token de login vale?
2. **esta sessão foi criada por ele?**
3. o acesso profissional está ativo?
4. a organização da sessão bate com a organização ativa do login?

A quarta recusou. Mas quando ela roda, a **segunda já provou** que quem conecta é
o autor daquela sessão — qualquer outra pessoa foi barrada antes. Ou seja: a
quarta só conseguia alcançar o próprio dono. Ela não protegia ninguém de
ninguém, e o que produzia era um profissional trancado para fora do que é dele,
sem ação possível na tela.

**Regra:** ao ler uma checagem de acesso, pergunte **quem ela ainda consegue
barrar, depois de tudo o que veio antes dela**. Se a resposta for "só o próprio
titular", ela não é proteção: é um portão virado para dentro.

E a correção depende de onde ela está — as duas metades importam:

- onde a autoria **já foi provada** antes dela, a checagem sai (ou vira registro);
- onde a autoria **não é perguntada em lugar nenhum**, a correção é
  **ACRESCENTAR** a pergunta que falta, nunca remover a que existe. Foi o caso do
  arquivamento do relatório: tirar o recorte ali deixaria qualquer conta gravar
  em sessão alheia, porque o recorte era a única guarda.

O corolário a casa já tinha escrito, e não tinha aplicado a todos os pontos: *"a
autoria vence a organização corrente [...]; trocar de organização não transfere a
autoria de nada."* Ver também 2.8 — corrigi as duas rotas de WebSocket e parei,
e foram os pontos que ficaram para trás que quase custaram o relatório da
consulta.

### 2.11 Um código, duas causas — e a recusa que não diz qual foi

**O caso, 20/09/2026.** O servidor fechava o WebSocket com `4401` em duas
situações: token de login inválido, e sessão pertencente a outra conta. A tela
tinha **uma** frase, a da segunda. O profissional leu "esta sessão pertence a
outra conta" e foi conferir de qual conta era a sessão — que estava certa —
enquanto o que tinha acabado era o login dele. As duas causas pedem ações
opostas: uma manda trocar de login, a outra manda entrar de novo no mesmo.

Pior, **o log tinha o mesmo defeito**. As seis causas de recusa gravavam a mesma
linha, `"outcome":"denied"`, sem o código. Descobrir qual havia sido exigiu
deduzir por um sinal indireto — o evento trazia `organization_id` preenchido, e
só um dos ramos passava contexto ao auditor. Custou uma investigação inteira,
com paciente esperando.

**Regra:** um código de erro é contrato de **uma** causa. Duas causas no mesmo
código produzem uma frase que está errada para metade dos casos, e quem a lê age
sobre a metade errada. E toda recusa grava **o próprio motivo**, não apenas o
fato de ter recusado: recusar em silêncio e recusar sem motivo registrado são a
mesma falha vista de dois lugares (regra 1.3).

**Como caçar:** para cada código que o sistema emite, liste os ramos que o
emitem. Mais de um ramo com semânticas diferentes é o defeito. E leia a frase
perguntando *a quem ela foi escrita* — no mesmo dia, o profissional recebia uma
recusa que mandava "pedir um novo link ao profissional", frase redigida para o
paciente.

### 2.12 O prazo contado do lugar errado

**O caso, 20/09/2026 — a causa raiz daquele dia.** A sessão de trabalho do
profissional expirava 8 horas depois do **login**, e nada a renovava: nem uso,
nem requisição, nem atividade. Quem entrou de manhã e atendeu à tarde teve o
prazo vencendo com o paciente do outro lado. A chamada continuou, porque é ponto
a ponto; o canal de análise passou a ser recusado, as medições pararam, e no fim
o relatório não gravou.

O prazo não estava errado. O **evento de partida** estava. Contado do último
uso, a mesma janela de 8 horas nunca interrompe quem está trabalhando e continua
expirando quem parou — nenhuma janela precisou ser alargada.

**Regra:** todo prazo tem um evento de partida, e ele quase nunca é o que se
escreveu primeiro. Pergunte: *isto mede inatividade ou mede tempo de vida?* Se o
que se quer é inatividade, contar do login está errado — e o erro só aparece no
dia mais longo de trabalho de alguém, que é o pior dia para aparecer.

---

## 3. Testes que valem alguma coisa

- **Afirme a garantia, não o mecanismo.** Um teste exigia literalmente o
  `rollback` do WebRTC; quando o rollback virou o defeito, o teste defendia o
  defeito. Reescrito para afirmar o que o usuário precisa que seja verdade.
- **E afirme-a em CADA ponto, não em algum ponto do arquivo.** Um teste conferia
  que `motivoDaRecusaDeSinalizacao` **aparece** em `LiveSession.tsx` — e aparecia,
  no socket da chamada. O socket de ANÁLISE, no mesmo arquivo, ignorava o código
  de fechamento e reconectava a cada cinco segundos contra uma recusa
  determinística, sem uma linha na tela. O teste passou o tempo todo, e a sessão
  correu sem medir nada. Presença no arquivo é mecanismo; a garantia era "todo
  socket que pode ser recusado lê a recusa", e essa se afirma varrendo os pontos
  um a um. Quando a correção for de regra e não de ocorrência (2.8), o teste
  **enumera** os pontos e obriga cada um a se declarar — o do recorte por
  organização lista as quatro funções que o usam, com o motivo de cada uma, e um
  uso novo quebra o teste.
- **Teste frágil é teste que mente.** Recorte por número de linha ou janela de
  caracteres quebrou duas vezes por crescimento de comentário. Recorte pelo
  **parser**, por nome de definição.
- **Um teste pode nascer impossível.** Uma asserção escrita com aspas duplas
  nunca casaria, porque `ast.unparse` normaliza para simples: o teste passou a
  vida inteira sem nunca ter podido falhar. Confira que o teste **falha** quando
  deve.
- **Teste a forma do arquivo, não só o tipo.** Uma edição mecânica deixou sete
  linhas com um `10` literal colado no começo. Era texto dentro de JSX: o
  typecheck aceitou, o build passou, e a única manifestação foi na tela, com
  paciente em atendimento.
- **Onde o teste real é pulado, escreva o estático.** O teste que exercita a
  gravação é pulado inteiro sem `duckdb` — então um valor a menos na lista
  passaria por toda a bateria local e só quebraria em produção. O substituto lê o
  `INSERT` com o parser e conta colunas, placeholders e valores.
- **Nunca reescreva um teste de segurança dentro de uma tarefa.** Ao encontrar
  `test_anonymous_datamart_..._excludes_literal_speech`, a saída certa não foi
  ajustá-lo: foi pôr o caminho novo atrás de uma chave **desligada por padrão**,
  travar as novas garantias no mesmo teste, e devolver a decisão ao dono.

---

## 4. Higienização — o lixo que atrapalha o raciocínio

Código morto não é neutro. Ele mente sobre o que o sistema faz, e faz perder
tempo em toda leitura seguinte. **Ao terminar um trabalho, limpe o que ele
deixou para trás.**

**Remova:**
- componente, módulo ou arquivo que ninguém mais importa;
- constante, estado ou variável que nada lê;
- coluna ou campo que nunca é preenchido — ou preencha, ou tire;
- CSS de classe que nenhuma página usa;
- teste que guarda uma decisão revogada (reescreva-o para a decisão nova, com o
  motivo da troca no docstring);
- caminho de código inalcançável, chave de configuração sem leitor, endpoint sem
  chamador.

**Nunca remova:**
- o comentário que conta o incidente. O registro histórico — *"isto aconteceu em
  03/09/2026, numa sessão real, e foi por isso que a regra é esta"* — é o que
  impede o defeito de voltar. Ele parece lixo e é a parte mais valiosa.
- a lápide de algo perigoso que foi retirado (ex.: o gerador de dados
  sintéticos), para ninguém o reintroduzir por ignorância.

**Ao remover, diga o que removeu e por quê.** Limpeza silenciosa é
indistinguível de perda de funcionalidade.

---

## 5. Conduta na entrega

Determinacao do dono, 06/09/2026, depois de uma entrega que eu declarei
pronta estando pela metade:

> nunca jamais deixe pela metade ou mesmo inconcluido a finaliização de um procedimento. comentarios como "procedimento totalmente inadeguado e inaceitavel "E você está certo: eu não corrigi tudo. Deixa eu mostrar o que faltou."" são absolutamente inaceitaveis jamais deixe uma situaçao deploravel como essa acontecer novamente.

Ela estava escrita no frontmatter deste arquivo, entre `description:` e o
`---`. Ali ela nao chegava a lugar nenhum: o YAML leu a frase como uma
TERCEIRA CHAVE do cabecalho — os dois-pontos dentro das aspas partiram a
linha em chave e valor — e o corpo carregado na sessao nunca a continha.
Instrucao no lugar errado e indistinguivel de instrucao dada, e essa e a
propria falha que ela descreve. Movida para ca em 08/09/2026, sem alterar
uma palavra.

- **Trabalhe em grupos.** Tarefa grande dividida em frentes independentes, uma
  por vez. Acumular contextos diversos degrada a qualidade antes de degradar
  qualquer outra coisa. Quando um grupo pede uma sessão nova, diga isso.
- **Verifique antes de afirmar.** Já afirmei sobre produção lendo um `.env`
  local, e estava errado. Ambiente local não é evidência sobre o servidor.
  Em 20/09/2026 repeti a falta noutra forma: dei o reinício do backend como causa
  provável de um incidente e **escrevi isso como conclusão** — inclusive numa
  anotação de memória — antes de ter conferido. O comando que derrubou a
  hipótese, `docker inspect -f '{{.State.StartedAt}} {{.RestartCount}}'`, existia
  o tempo todo e custava um minuto. **Hipótese nomeada como hipótese não custa
  nada; hipótese entregue como causa faz o outro lado agir sobre ela.** Antes de
  chamar alguma coisa de causa, pergunte que comando a falsificaria — e rode-o.
- **Meça antes de apertar ou afrouxar.** Escolher um limiar sem dado é escolher
  no escuro. Se o dado ainda não existe, diga que não existe e diga qual número
  o produziria.
- **Confirme o que é difícil de reverter.** Deploy com paciente esperando, escrita
  em tabela compartilhada, remoção de garantia — pergunte antes.
- **Relate o resultado como ele é.** Se o teste falhou, mostre a saída. Se uma
  parte ficou de fora, diga qual e por quê.
- **Deploy:** leia o `docker-compose.yml` antes de montar o comando. `froid-site`
  é bind mount e entra com `git pull`; `froid-frontend` e `froid-backend` são
  imagens e exigem `build`. Rebuild de backend derruba sessão ativa.

### 5.1 Um commit, uma decisão separada

Em 04/09/2026 publiquei os dois mapas da face, corrigi vinte arquivos de
afirmação sem origem no código e reorganizei o header do site — **tudo num
commit só**. O dono perguntou o óbvio antes de aprovar: *"e se o layout não
ficar adequado, dá para voltar?"* Não dava: um `git revert` naquele commit
levaria junto a página nova e as correções.

O erro não foi de código. Foi entregar como um bloco duas decisões que o dono
toma separadamente: **o conteúdo** e **a aparência**. Ele pode querer o
primeiro e recusar o segundo.

**Ao montar o commit, separe o que o dono decide separado** — separando na hora
de commitar, com os arquivos como já estão na árvore. Os pares que quase sempre
se separam:

| Junto no trabalho | Separado no commit |
|---|---|
| conteúdo novo | layout/estilo que o acomoda |
| correção do defeito | refatoração que veio a reboque |
| funcionalidade | higienização que ela permitiu |
| dado novo | mudança de fórmula que o consome |

**Não desfaça o trabalho já feito para provar que dá para desfazer.**
Determinação do dono, 09/09/2026: o ensaio de reversão — resetar o commit,
reconstruir o estado intermediário arquivo por arquivo, rodar
`git revert --no-commit` e depois `git revert --abort` — consome tempo demais e
atrapalha o trabalho. Não rode nada disso por iniciativa própria. Se o dono
pedir a separação de um commit já feito ou o ensaio da volta, aí sim faça.

**O que continua valendo, porque não custa tempo:** ao entregar, diga quais
decisões vieram juntas no mesmo commit e o que uma volta devolveria — no caso
acima, o header voltaria a quebrar em duas linhas, agora com um link a mais.
Reverter restaura o estado anterior, não um melhor, e quem decide precisa saber
disso antes de decidir.

---

## 6. Armadilhas desta casa

- **Heredoc e barra invertida:** `\n` colapsa e quebra o arquivo gerado. Já
  quebrou uma string TypeScript, um teste Python e uma regex. Use a ferramenta
  de escrita de arquivo, ou `chr(10)` / `chr(92)`.
- **Encoding:** os HTML são UTF-8. Depois de editar, procure mojibake
  (`Ã§`, `Ã£`, `â€"`). Se apareceu, desfaça e refaça.
- **`white-space: pre-wrap`:** dentro de um template literal, o recuo do código
  é conteúdo. A frase *"Seu / profissional não registrou"* saiu partida na
  quarta página de um relatório real.
- **A fronteira clínica é inviolável.** Nenhum texto pode sugerir que o
  empregador lê resposta individual de trabalhador. E o produto não fala de si
  dentro do prontuário: um resumo descreveu "problemas com gráficos e a falta de
  apuração de índices acústicos" no documento pessoal de um paciente.
- **O documento do paciente é pauta, não relatório técnico.** Vinte e uma linhas
  de MFCC e ZCR não dizem nada a ele e, a `0,00`, destroem a credibilidade das
  duas leituras que estavam certas.
- **Terminal em dois passos.** "Conecte e cole" numa frase só fez o bash do
  servidor cair no PowerShell local — `$(date)`, `&&` e `tail` quebraram e um
  diretório nasceu por engano. Toda instrução diz **onde** roda: Git
  Bash/PowerShell **local**, ou **console do servidor** (após `ssh froid`,
  prompt `root@...`). Mostre a troca de prompt ao entrar, mande **um** comando
  por bloco (dois `docker compose run` colados: o primeiro engole a linha do
  segundo pelo stdin) e **sem barra de continuação** de linha. E `.env` editado
  só vale depois de `docker compose up -d` — a variável é lida na subida.

---

## 7. Entregar em fases, com gate (quebrar a implementação)

A unificação do Psique V2 (Fases 1→7, set–out/2026) ensinou a forma. Mudança
grande que toca dinheiro, dado ou produção **não entra num lance** — vira uma
sequência de fases, e cada fase é uma unidade fechada:

1. **Desenha primeiro, aterrado no código real.** Antes de uma linha, um
   documento (`docs/...-faseN-desenho.md`) que lê o código existente e aponta
   `arquivo:linha` — o que entra, o que **não** entra (fronteira explícita) e os
   pontos de religamento. Desenho que não cita o código é palpite.
2. **As decisões do dono bloqueiam o início.** Toda bifurcação que muda o que se
   constrói (esgotamento bloqueia ou entrega?; aposentar ou preservar um portão?)
   é pergunta ao dono — `AskUserQuestion`, recomendação como primeira opção, com
   o custo de cada caminho. Marque `DECIDIDO em <data>` no documento. Não presuma
   a decisão "para adiantar".
3. **Mecanismo agora, execução em massa depois.** Separe a peça reutilizável
   (migração + serviço + testes, que pode entrar **dormente**, sem chamador) da
   ativação que acopla a outras fases. A 7.3 entregou o backfill como função
   dormente e commitada; converter todas as orgs ficou para a janela da 7.4,
   porque converter uma org sem unificar o comércio a deixaria sem como comprar.
   Entregar o mecanismo cedo é seguro; executar em massa é que pede a janela.
4. **Caminho duplo temporário e explícito.** Ao religar, roteie por estado
   (`credit_model='psique_v2'` → V2; o resto → V1), nunca um big-bang. O caminho
   duplo é comentado como temporário e some quando a fase seguinte migra o resto.
5. **Commit só com a palavra; publique cedo; produção só colada pelo dono.**
   "commit" é gatilho explícito (o recorte em 5.1). Empurre para o origin assim
   que commitar — sessão simultânea reseta trabalho não publicado. Nada em
   produção sem o dono colar no console; a janela é dele.
6. **Cada fase fecha com evidência e janela própria:** teste (seção 8) →
   apresentação para commit → roteiro de janela rotulado (seção 6, terminal em
   dois passos) → gate. A fase seguinte só começa no próximo gate.

## 8. Teste contra PostgreSQL real — e em Windows E Linux

Máquina de crédito, esquema, RLS, `SECURITY DEFINER`: prova-se contra
**PostgreSQL descartável real**, nunca mock. E em **duas plataformas** — o
programa fechou "158/158 contra `postgres:16` Linux", e a paridade é parte do
contrato. Validar só no Windows é meia validação (caso real, 02/10/2026:
perguntaram "você testou no Linux?" e a resposta honesta era não).

**Windows (binário portátil em `.codex-tmp/psique-postgres16`):** `initdb -U
psique_test -A trust`; role `froid_runtime` `NOSUPERUSER NOBYPASSRLS NOLOGIN`
criada **fora** de transação; banco-âncora com prefixo obrigatório
`psique_v2_test_` (a guarda do fixture exige); `FROID_PSIQUE_TEST_DATABASE_URL`;
pytest no venv `.codex-tmp/psique-v2-venv`. Encerrar (`pg_ctl stop`) e **remover
o cluster** no fim — cluster órfão não se sonda nem se reusa.

**Linux (Docker):** `postgres:16` com `POSTGRES_USER=psique_test`,
`POSTGRES_DB=psique_v2_test_base` (prefixo!), `POSTGRES_HOST_AUTH_METHOD=trust`;
criar `froid_runtime` via `docker exec ... psql`; rodar pytest dentro de
`python:3.13-slim` com **`--network container:<pg>`** (o banco vira `127.0.0.1`
e satisfaz a guarda de host do fixture). Derrubar o container no fim.

**As quatro armadilhas que custaram uma sessão (02/10/2026), cada uma um caso:**
- **Mount com espaço no caminho.** O repo mora em `.../FROID GITHUB V5/FROID`; no
  Git Bash o `docker -v` com espaço falha e `-w /app` vira
  `C:/Program Files/Git/app`. Copie o fonte para um caminho **sem espaço** (o
  scratchpad), monte com `MW=$(pwd -W)` + `MSYS_NO_PATHCONV=1`, destino `-w /app`.
- **Dependência pinada sem wheel para o Python do container.** `pydantic==2.7.4`
  não tem wheel para py3.13 → o pip tenta compilar `pydantic-core` com Rust
  (ausente no slim) → aborta inteiro → `No module named pytest`, que **parece**
  erro de teste e é de instalação. Não pine o que o resolvedor pode escolher.
- **Cópia incompleta parece regressão.** Copiar só `*.py`/migrations/tools/tests
  e esquecer `config/` (catálogo) dá 73 "errors" de fixture
  (`FileNotFoundError: psique_pricing_v2.json`) — zero a ver com o código. As
  fases de site/compose ainda pedem `froid-site` e `docker-compose.yml` da raiz.
  Monte o repo inteiro, ou copie também o que vive fora de `froid-server`.
- **`tail` esconde a causa.** `... | tail` no container guarda só o resumo e o
  motivo do erro some. Para diagnosticar, capture o **bloco de erro** inteiro, ou
  `--collect-only` para separar erro de import de erro de fixture. (E
  `set_config(...,true)` só vale dentro de transação explícita — probe em
  autocommit perde a GUC e dá falso `CONTEXT_MISMATCH`.)

**O sinal limpo:** rode a suíte-alvo **isolada, com as deps certas**, e distinga
falha de código de artefato de arnês (dep ou arquivo faltando). Um número de
"falhas" só vale depois que você provou que não é o seu setup.

## 9. Migrations de ledger imutável e a máquina de dinheiro

Da 047 (consumo de sessão) e 048 (backfill V1→V2):

- **CHECK fechado amplia-se copiando-se verbatim.** Para acrescentar um tipo de
  evento a um `credit_ledger` com `version_semantics`/`event_type_check`
  fechados, a migração faz `DROP`/`ADD` copiando a **definição corrente inteira,
  verbatim**, mais a linha nova. Só **uma** migração por vez mexe nesses CHECKs;
  copiar de uma versão velha reverte as linhas das migrações do meio. Ampliar
  (não restringir) nunca falha sobre dados existentes.
- **Função nova e focada, não reescrever o comando grande.** O consumo de sessão
  virou `psique_v2_session_charge` separada, não um ramo no comando de 250 linhas
  — menor superfície, menos risco ao que já estava provado.
- **Prove a aplicação INCREMENTAL, não só o encadeamento inteiro.** O fixture
  aplica 001→N de uma vez, mas produção aplica **só a migração nova** sobre o
  estado já aplicado. Teste exatamente isso: `--through` da nova sobre um banco
  em N-1, confirme que rodou **só ela** e que **reaplicar é no-op** (o runner
  confere checksum do log; arquivo alterado depois de aplicado aborta).
- **Parâmetro de função não pode ter nome de coluna tocada no corpo.**
  `ever_purchased` (parâmetro) × `ever_purchased` (coluna) no `UPDATE` deu
  `42702 referência ambígua`, mascarado como `PSIQUE_STORAGE_ERROR`. Renomeie o
  parâmetro (`has_purchased`).
- **Valide como o papel restrito real.** `SECURITY DEFINER` roda como o dono e
  **esconde** a falta de grant em runtime. Rode os testes como `froid_runtime`
  (SET ROLE / DSN restrito), senão o grant que faltaria em produção passa verde.
- **Preserve a trilha; não apague para converter.** O backfill vira a carteira
  V1→V2 **sem** DELETE do histórico (o gatilho de imutabilidade só barra *novas*
  linhas v1 sob carteira v2). Converter apagando foi o caminho da demo, não o da
  frota.

---

## 10. Antes de dizer que terminou

1. O que eu escrevi é **lido** por alguém? (padrão 2.1)
2. Se a peça falhar, alguém **fica sabendo**? (padrão 2.2)
3. Algum número aqui pode ter sido **suposto**? (regra 1.1)
4. O rótulo descreve o que a coisa **faz**? (padrão 2.4)
5. O teste afirma a **garantia** e falha quando deve? (seção 3)
6. Este trabalho deixou **lixo** para trás? (seção 4)
7. O que ficou **de fora**, e eu disse isso? (seção 5)
8. As decisões que o dono toma separadas entraram em commits **separados**? (seção 5.1)
9. Esta checagem de acesso ainda consegue barrar **alguém além do próprio titular**? (padrão 2.10)
10. Cada recusa diz **qual** das causas foi — na tela e no log? (padrão 2.11)
11. Este prazo mede **inatividade** ou tempo de vida, e parte do evento certo? (padrão 2.12)
12. O que eu chamei de **causa** foi conferido, ou é hipótese que escapou como conclusão? (seção 5)
13. Provei contra PostgreSQL real, em **Windows e Linux**, e o número não é artefato de arnês (dep/arquivo faltando)? (seção 8)
14. A migração aplica **incremental** — só ela sobre o estado atual — e **reaplicar é no-op**? (seção 9)
15. Esta fase respeitou o gate: desenho aterrado, decisão do dono, commit só com a palavra, produção só colada? (seção 7)
