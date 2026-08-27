# Como a empresa opera uma campanha NR-1 no FROID

Nota operacional. Responde as perguntas que aparecem quando alguem esta com a
tela aberta, e nao as de principio — para essas, ver a nota de riscos
psicossociais e a de leitura do resultado.

Escrita depois de um teste ponta a ponta completo, em que a maioria das
duvidas nao era sobre a norma: era sobre o que clicar, o que o sistema guarda e
o que nao tem volta.

## A ordem dos atos, e por que ela e essa

1. **Estrutura da empresa** — estabelecimentos (enderecos) e setores. E sobre
   ela que os recortes do relatorio sao calculados. Departamento no mesmo
   endereco nao e estabelecimento: e setor.
2. **Criar a campanha**, que nasce em rascunho e nao coleta nada.
3. **Abrir a coleta** — segundo ato, deliberado. E ele que comeca a valer a
   janela.
4. **Emitir os convites** — um link unico por pessoa.
5. **Distribuir** os links. Quem distribui e a empresa, nunca o FROID.
6. **Encerrar a coleta** — e o encerramento que torna o resultado legivel.
7. **Gerar o inventario** e, a partir dele, o plano de acao.

## O que nao aceita edicao depois de criado

A campanha nao tem rota de atualizacao. Tres campos ficam congelados no que foi
gravado, e conferi-los antes de criar evita refazer tudo:

| campo | por que congela |
| --- | --- |
| efetivo do periodo de referencia | e o denominador que define a amostra exigida e vai para o inventario |
| aviso de finalidade | e o texto que o trabalhador le antes da primeira pergunta |
| janela de coleta | abertura e fechamento entram no documento |

Trocar qualquer um deles exige campanha nova.

## O FROID nunca recebe nome de trabalhador

Nao ha campo, nao ha importacao, nao existe.

A empresa fornece a **matricula** (ou codigo interno). O servidor a transforma
em pseudonimo por HMAC com chave propria e devolve um link por matricula. O
par matricula-link nao e gravado em lugar nenhum do FROID: do link guarda-se so
o resumo criptografico, e da matricula so o pseudonimo.

Essa ausencia e o que sustenta o anonimato. Nao e politica de acesso, que
alguem poderia mudar: e dado que nao existe.

Para atribuir o setor, a lista aceita `matricula;setor` — o setor e casado pelo
nome ou pelo codigo interno da unidade, sem diferenciar maiuscula. Sem o
segundo campo o convite fica sem setor: a pessoa responde e conta para a
campanha, mas nao forma recorte proprio.

## O arquivo de links, e por que ele precisa ser apagado

Ao emitir, a tela mostra os links UMA vez e oferece o arquivo `matricula;link`.
Esse arquivo e o unico lugar do mundo onde os dois aparecem juntos.

Isso e necessario — sem o par ninguem consegue entregar o convite a pessoa
certa — e e por isso que o par existe do lado da empresa, e nao do nosso. Mas
enquanto o arquivo existir, quem o tiver consegue abrir cada link e ver qual
recusa, descobrindo **quem** ja respondeu. Nao o que respondeu: isso ninguem
consegue, nem nos.

Nao ha correcao tecnica possivel para isso. O controle e de guarda: distribuiu,
apagou. O arquivo baixa com o aviso no proprio nome.

## O convite e de uso unico e pertence a uma pessoa

Um link respondido para de funcionar. Reabri-lo — no mesmo aparelho ou em
outro — devolve "convite indisponivel".

Nao ha amarracao a aparelho: o mesmo link ainda nao respondido abre no celular,
no computador, onde for. O que nao se repete e a resposta.

Publicar um unico link no mural, no grupo ou na intranet nao funciona: o
primeiro que responder consome aquele convite e os demais recebem a recusa.

**A mensagem de recusa e deliberadamente igual** para token invalido, convite ja
usado, fora da janela e campanha encerrada. Distinguir os casos permitiria
descobrir quem respondeu perguntando ao sistema.

## Quem perdeu o link

A tela de campanha tem a reemissao: cola-se a matricula, e ela recebe um link
novo. Tres coisas a saber:

- **o link anterior morre** no instante em que o novo e gravado;
- **quem ja respondeu nao recebe link novo**, e a recusa e do banco. Um segundo
  link para quem ja respondeu faria a mesma pessoa contar duas vezes na coorte;
- a resposta **nao diz por que** alguem nao foi reemitido. "Sem convite
  pendente" cobre quem ja respondeu e quem nunca foi convidado, e o sistema nao
  afirma qual dos dois.

O setor atribuido na emissao original e mantido. Trocar o setor de quem ja foi
convidado exige campanha nova.

## Encerrar nao tem volta

Nao existe rota que devolva uma campanha encerrada ao estado aberto. Ao
encerrar, os convites pendentes param de funcionar.

Em troca, e o encerramento que libera o resultado. Enquanto a coleta esta
aberta o painel mostra apenas adesao — e isso e protecao, nao limitacao: uma
coorte que ainda cresce pode ser deduzida uma resposta por vez, observando o
agregado antes e depois de cada nova resposta.

Ordem pratica: responda tudo o que precisa ser respondido, depois encerre.

## O que fica guardado, e por quanto tempo

O inventario e seu historico precisam sobreviver **vinte anos** (subitem
1.5.7.3.3.1). Por isso nada do modulo se exclui: unidade sai da estrutura por
arquivamento, campanha encerra mas nao se apaga, e o banco recusa a exclusao
das linhas que o inventario referencia.

As respostas brutas sao outra coisa. A norma exige vinte anos do INVENTARIO, e
nao das respostas que o produziram — depois de consolidado, a resposta
individual nao responde nenhuma pergunta que o agregado nao responda. Ha
ferramenta propria para purga-las apos a consolidacao.

## Erros que o teste real produziu, e como evita-los

- **Hora em branco na janela de coleta.** O seletor do navegador deixa a hora
  vazia quando so o dia e escolhido, e o campo inteiro conta como vazio. Hoje a
  janela nasce preenchida.
- **Aviso de finalidade deixado em branco** por parecer ja preenchido: era o
  texto-fantasma do campo. O servidor anexa a base legal e a campanha abre, mas
  o trabalhador le so o artigo da LGPD, sem uma palavra da empresa. Hoje o
  campo e obrigatorio.
- **Lista de matriculas sem o setor**, o que impede qualquer recorte por setor
  naquela campanha.
- **Campanha aberta e esquecida** sem convites. Ela nao coleta nada e ainda
  aparece no painel.
