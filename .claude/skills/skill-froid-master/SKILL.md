---
name: skill-froid-master
description: As regras de conduta e os padrões de defeito apurados no FROID, para escrever, revisar, auditar ou higienizar código deste e dos próximos sistemas. Use antes de mexer em qualquer caminho que produza número, texto ou decisão que alguém vá ler como verdade.
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

## 3. Testes que valem alguma coisa

- **Afirme a garantia, não o mecanismo.** Um teste exigia literalmente o
  `rollback` do WebRTC; quando o rollback virou o defeito, o teste defendia o
  defeito. Reescrito para afirmar o que o usuário precisa que seja verdade.
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

- **Trabalhe em grupos.** Tarefa grande dividida em frentes independentes, uma
  por vez. Acumular contextos diversos degrada a qualidade antes de degradar
  qualquer outra coisa. Quando um grupo pede uma sessão nova, diga isso.
- **Verifique antes de afirmar.** Já afirmei sobre produção lendo um `.env`
  local, e estava errado. Ambiente local não é evidência sobre o servidor.
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

---

## 7. Antes de dizer que terminou

1. O que eu escrevi é **lido** por alguém? (padrão 2.1)
2. Se a peça falhar, alguém **fica sabendo**? (padrão 2.2)
3. Algum número aqui pode ter sido **suposto**? (regra 1.1)
4. O rótulo descreve o que a coisa **faz**? (padrão 2.4)
5. O teste afirma a **garantia** e falha quando deve? (seção 3)
6. Este trabalho deixou **lixo** para trás? (seção 4)
7. O que ficou **de fora**, e eu disse isso? (seção 5)
