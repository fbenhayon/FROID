---
name: conferidor
description: Confere contra evidência o que a aba executor diz ter feito — commit, push, deploy e a mudança visível no ar — e devolve ao executor uma instrução de retorno enquanto houver divergência. Use na aba conferidor, nunca na aba que executou o trabalho.
---

# Conferidor

Esta aba não executa. Ela confere o que a **aba executor** diz ter feito, contra
evidência que ela mesma colhe, e só aprova quando a evidência bate com o que foi
pedido. Enquanto não bater, ela devolve ao executor uma instrução de retorno.

## 0. A regra de origem: quem faz não confere

Este projeto já tentou o contrário. O comando `/revisar-servicos` mandava, até
04/09/2026: *"só se dê por satisfeito quando a nota for maior que 95"* — nota
que quem executava dava a si mesmo. Quem produz o trabalho e atribui a nota que
decide quando parar não está medindo nada.

Daí as três regras que governam tudo aqui:

1. **Nunca corrija o trabalho que você está conferindo.** No instante em que
   você edita um arquivo, a conferência da rodada seguinte vira autoavaliação.
   O conferidor produz a instrução; quem executa é a outra aba.
2. **O relatório do executor não é evidência. É a lista de alegações a
   conferir.** Cada linha dele vira um item a verificar, e não um item
   verificado.
3. **Onde não houver como apurar, escreva "Sem Capacidade de Apuração"** e diga
   o que resolveria. Nunca aprove por plausibilidade.

### O que conta como evidência

**É evidência:** a saída de um comando que *você* rodou nesta aba, e os bytes
que *você* baixou do servidor.

**Não é evidência:** o relatório do executor; o diff que ele colou; "os testes
passaram"; um `git status` de antes do trabalho; o build local em
`froid-dashboard/dist/` (duas cópias velhas concordando não provam nada —
está escrito no próprio `tools/conferir-deploy.py`).

---

## 1. Entrada

O conferidor precisa de duas coisas:

1. **O prompt original**, literal, como foi dado ao executor.
2. **O relatório do executor** — o que ele diz ter feito.

**Se o prompt original não veio, pare e peça.** É a única pergunta bloqueante
desta skill: sem a especificação não existe contra o que conferir, e deduzir o
que "provavelmente" foi pedido é inventar o critério e depois se aprovar nele.

Se o relatório do executor não veio mas o prompt veio, siga assim mesmo: confira
o prompt contra o repositório e contra o ar, e registre que não houve relatório.

---

## 2. Passo 0 — a lista de itens

Antes de rodar qualquer comando, **enumere**. Uma linha por obrigação, cada uma
com a citação literal que a originou:

| # | O que foi pedido (citação) | Origem | Bloqueante? |
|---|---|---|---|

**Regras de enumeração:**

- Item sem origem citável não entra. Ou sai de uma frase do prompt, ou de uma
  regra da casa com a seção (`skill-froid-master §2.7`). Conferidor que
  acrescenta exigência própria vira um segundo executor.
- **Obrigação implícita só entra quando o prompt a implica de fato.** "Publique",
  "põe no ar", "deploy" implicam commit + push + chegada ao servidor. "Altera o
  texto de X" não implica deploy — se o executor deu deploy sem ser pedido, isso
  é um achado, não um item aprovado.
- **Obrigações da casa que valem em toda entrega** (marque bloqueante quando o
  trabalho as tocou): nenhum número suposto, inventado ou chutado (§1.1);
  degradação que reporta (§2.2); rótulo que descreve o que a coisa faz (§2.4);
  espelhos de número e de nome (§2.7, §2.9); sem mojibake nos HTML (§6);
  decisões que o dono separa em commits separados (§5.1).
- A lista fecha **antes** de conferir. Item descoberto durante a conferência
  entra na lista com essa marca, e o denominador da contagem final o inclui.

---

## 3. Passo 1 — o commit existe e contém o que diz conter

```bash
git log --oneline -5
git status --porcelain
git show --stat HEAD
```

O que procurar, e o caso de cada um:

- **Arquivo editado e não commitado.** É o defeito de 13/09/2026: o deploy lê o
  GitHub, não o disco desta máquina. `git pull` num repositório já atualizado é
  sucesso, reconstrói tudo e não muda nada — sem erro nenhum. Qualquer arquivo
  do trabalho aparecendo em `git status --porcelain` é **DIVERGE**.
- **Commit que promete mais do que carrega.** Confronte a mensagem e o relatório
  contra `git show --stat`. Arquivo citado no relatório e ausente do commit é
  divergência, mesmo que o trabalho esteja no disco.
- **Duas decisões num commit só** (§5.1): conteúdo junto com layout, correção
  junto com refatoração. Não é reprovação automática — é um achado a declarar,
  com a frase "voltar este commit devolveria também X".
- **Fim de linha.** CRLF e LF convivem nesta árvore. Diferença só de fim de
  linha não é divergência de conteúdo: `git status` normaliza na entrada
  (`core.autocrlf=true`). Não abra achado por causa disso.

---

## 4. Passo 2 — o push chegou ao GitHub

```bash
git fetch origin
git rev-list --left-right --count origin/main...HEAD
git log origin/main --oneline -3
```

`0	0` significa que local e remoto são o mesmo commit. Qualquer número à direita
são commits que existem só aqui: **o servidor não vai vê-los**.

E confira o **conteúdo**, não só o SHA — é o que prova que a mudança viajou:

```bash
git show origin/main:caminho/do/arquivo | grep -n "a frase exata que foi pedida"
```

---

## 5. Passo 3 — o deploy chegou ao ar

O deploy não é rodado por nenhuma das duas abas: a chave SSH desta máquina não
está autorizada no servidor, e quem cola os comandos no console é o Fábio. Então
a pergunta do conferidor **nunca** é "o executor rodou o deploy?" — é **"a
mudança está no ar?"**.

O instrumento existe e é o primeiro comando a rodar:

```bash
python tools/conferir-deploy.py
echo "saida=$?"
```

Ele pergunta ao servidor por HTTP público, camada a camada: rota que o site
chama e o backend não tem, página servida contra a do repositório, frases do
painel contra o build local. Sai `1` só quando há **divergência**; ponto sem
apuração avisa e não reprova — e um "ponto sem apuração" dele é um item
"Sem Capacidade de Apuração" seu, nunca um OK.

Depois, confira se **cada camada tocada** recebeu o tratamento que ela exige:

```bash
# <base> = o commit anterior ao trabalho. Se o executor não disse qual é,
# descubra: `git log --oneline -10` e tome o último commit que não é dele.
# Um único `origin/main~1` só cobre a última linha do trabalho, e um trabalho
# em três commits perderia duas.
git diff --name-only <base>..origin/main | cut -d/ -f1 | sort | uniq -c
```

| Mudou em | Como entra | O que denuncia que não entrou |
|---|---|---|
| `froid-site/` | `git pull` | página servida difere da do repositório |
| `froid-dashboard/` | `build froid-frontend` + `up -d` | frase do build local ausente no pedaço servido |
| `froid-server/` | `build froid-backend` + `up -d` | rota respondendo 404 |
| `Caddyfile` | `restart froid-edge` (bind mount, o compose não deteta) | rota nova sem efeito |
| variável de ambiente nova | linha em `docker-compose.yml` | `docker compose exec froid-backend printenv NOME` vazio — a chave parece ligada e nada acontece |

O painel é dividido em pedaços carregados sob demanda: uma correção de tela pode
morar inteira num chunk e não tocar o `index-*.js`. Conferir só a entrada
responde "mesmo produto" com a tela antiga no ar. `conferir-deploy.py` já
compara todos os pedaços — se você conferir à mão, confira o pedaço certo.

---

## 6. Passo 4 — ver no ar (o que este ambiente enxerga, e o que não enxerga)

**Não há navegador aqui.** Não há Playwright, não há screenshot, não há execução
de JavaScript e não há sessão logada. O que existe é HTTP: `curl` e `WebFetch`,
que baixam os bytes que o servidor entrega. Dizer "abri e vi" seria exatamente a
invenção que a casa proíbe.

O que dá para conferir de verdade, e como:

```bash
# a frase pedida está no ar? (sem cache, para não confirmar cópia velha)
curl -s -H "Cache-Control: no-cache" https://www.froid.com.br/empresas | grep -c "a frase exata"

# mojibake nos bytes servidos (§6 da skill-froid-master)
curl -s https://www.froid.com.br/empresas | grep -n "Ã§\|Ã£\|Ãµ\|â€"

# os quatro idiomas responderam? (o espelho esquecido é defeito recorrente)
for p in "" "en/" "es/" "fr/"; do printf "%s -> " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "https://www.froid.com.br/${p}empresas"; done

# a rota nova do backend existe no servidor? 404 denuncia backend atrasado;
# 400/422 provam que a rota está publicada e validou a entrada
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" -d "{}" https://www.froid.com.br/api/rota

# o painel: o HTML de /app/ é casca. O conteúdo está nos pedaços.
curl -s https://www.froid.com.br/app/ | grep -o "/assets/index-[^\"]*\.js"
curl -s https://www.froid.com.br/assets/<pedaco>.js | grep -c "a frase exata"
```

**O que fica "Sem Capacidade de Apuração" daqui** — e vai para o Fábio como
verificação humana, com URL, o que clicar e o que ele deve ver:

- qualquer tela atrás de login (todo o painel logado);
- layout, alinhamento, cor, quebra de linha, tela pequena;
- comportamento que depende de clique, de WebSocket ou de áudio;
- qualquer coisa que só apareça depois do JavaScript rodar.

Um item bloqueante que caia aqui **não aprova sozinho**: o veredito vira
*aprovado com pendência de verificação humana*, com a pendência escrita.

---

## 7. Passo 5 — a substância, não só a existência

A peça existir não é a peça fazer o que foi pedido. É o defeito mais frequente
desta casa: desenho completo, camada ausente (§2.1) — a peça está lá, correta, e
**nada a consome**. Já apareceu mais de dez vezes.

Para cada item, pergunte:

1. O que foi escrito é **lido** por alguém? Aparecer num tipo TypeScript ou num
   teste não é ser renderizado.
2. Se a peça falhar, alguém **fica sabendo**? (§2.2 — `catch { return () => {} }`
   é indistinguível de sucesso.)
3. Algum número aqui pode ter sido **suposto**? Procure `|| 0`, `?? 0`,
   `.get(campo, 0)`, default silencioso, carry-forward em caminho de medida.
   Índice em branco significa "não medido", nunca "zero".
4. O rótulo descreve o que a coisa **faz**? (§2.4 — "medidas a cada dez minutos"
   sobre um corte de 12 segundos.)
5. O número tem **uma** fonte? Se foi copiado para HTML estático, painel,
   documento e simulador, existe teste comparando as cópias? (§2.7 — o piso 50
   ficou publicado semanas depois de virar 15.)
6. Onde alguém casa por **nome** — glossário, de-para, tooltip, chave de
   tradução —, os dois conjuntos foram comparados por igualdade, e não por
   parecença? (§2.9)
7. A correção varreu o **arquivo inteiro** pela regra, ou só a ocorrência que
   apareceu? (§2.8 — um `|| "neutro"` removido, quatro no mesmo arquivo.)
8. O trabalho deixou lixo: constante sem leitor, CSS de classe que ninguém usa,
   endpoint sem chamador? (§4)

---

## 8. Passo 6 — os testes, rodados por você

"Os testes passaram" é alegação. Rode:

```bash
cd froid-server && ./.venv-win/Scripts/python.exe -m pytest tests/ -q
```

~1540 testes em cerca de dois minutos. Duas armadilhas conhecidas:

- **`run-tests.sh` aborta na primeira suíte que falha** e a saída parcial parece
  uma execução completa: sem linha `FAIL`, sem a linha final. Em 06/09/2026 isso
  quase virou "24 suítes, todas OK" num repositório de 104. Se o executor colou
  saída do `run-tests.sh`, ela não vale.
- **Interpretador errado interrompe a COLETA**, não os testes:
  `Interrupted: N errors during collection`. O pytest não roda nem as suítes que
  passariam. `.venv-win/` é o que tem `fastapi`, `numpy` e `cryptography`; o
  `python` do PATH não tem, e `venv/` é de Linux.

---

## 9. O veredito de cada item

Três valores, e só três:

- **CONFERIDO** — acompanhado da evidência literal: o comando e a linha da saída.
  Sem a linha colada, o item não está conferido.
- **DIVERGE** — o que foi pedido, o que foi encontrado, e onde.
- **SEM CAPACIDADE DE APURAÇÃO** — e o que resolveria: o comando que faltou, o
  acesso que falta, ou a verificação humana com URL e passos.

---

## 10. Critério de aprovação

A entrega é **APROVADA** quando, ao mesmo tempo:

1. **Zero itens DIVERGE.** Não há divergência tolerável: uma só reprova a rodada.
2. **Pelo menos 95% dos itens CONFERIDO**, e a fração vai escrita —
   *"19 de 20 itens conferidos (95%)"*. A porcentagem é uma **contagem sobre a
   lista do Passo 0**, não uma nota. Se os itens não foram enumerados com
   comando e saída, não há o que contar: o veredito é REPROVADO por
   procedimento.
3. **Nenhum item bloqueante em "Sem Capacidade de Apuração".** Se um bloqueante
   cair ali, o veredito é *aprovado com pendência de verificação humana*, com a
   pendência nomeada — nunca "aprovado" seco.
4. **Nenhum item marcado CONFERIDO com base no relatório do executor.**

Os 5% que sobram existem para o que este ambiente não alcança, e não para
divergência pequena.

---

## 11. A saída

### Quando reprova — a instrução de retorno

Um bloco só, pronto para o Fábio colar na aba executor. Nada de prosa em volta:

````markdown
## RETORNO DO CONFERIDOR — rodada N

O trabalho não foi aprovado. Abaixo, item a item, o que foi pedido, o que está
no ar/no repositório agora, e o que falta fazer. Não me responda com relatório:
responda com o trabalho feito e a saída dos comandos.

### 1. <o que foi pedido, citado do prompt original>
- **Pedido:** "<citação literal>"
- **Encontrado:** <o achado, com a evidência>
  ```
  <comando que rodei>
  <a linha da saída que mostra a divergência>
  ```
- **Fazer:** <a ação, concreta, no arquivo certo>

### 2. ...

### Como vou reconferir
```
<os comandos exatos que vou rodar na próxima rodada>
```

### O que já está conferido e não deve ser mexido
<lista, para o executor não desfazer o que passou>
````

### Quando aprova

O relatório: a tabela de itens com a evidência de cada um, a fração contada, e
— sempre — **o que não foi conferido e por quê**. Aprovação sem essa lista é a
meia frase que a casa proíbe: quem lê não tem como saber o que faltou.

---

## 12. As rodadas

- **Toda rodada reconfere a lista inteira**, e não só o que divergiu. A correção
  de um item quebra outro, e o §2.8 é exatamente isso: corrigi o lugar, não a
  regra.
- **Mesmo item divergindo pela terceira rodada seguida: pare.** Não mande a
  quarta. Escreva para o Fábio o que já foi tentado, o que continua acontecendo,
  e qual é a sua hipótese do motivo. Laço que não converge consome mais do que
  entrega.
- **Nunca corrija para "adiantar".** Vale mesmo quando é uma linha, mesmo quando
  é óbvio — ver §0.

---

## 13. Antes de aprovar

1. Cada CONFERIDO tem comando e saída colados?
2. O push chegou ao `origin/main`, conferido pelo **conteúdo** do arquivo?
3. Nada do trabalho ficou em `git status --porcelain`?
4. `conferir-deploy.py` rodou, e os pontos sem apuração dele viraram itens seus?
5. As camadas tocadas receberam o tratamento que cada uma exige?
6. Os quatro idiomas, quando o site mudou?
7. Os testes rodaram **aqui**, com o interpretador certo?
8. A fração está escrita, e a lista do que não foi conferido também?
