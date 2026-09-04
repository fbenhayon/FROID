---
name: revisar-servicos
description: Revisão minuciosa dos textos e da substância dos descritivos de serviço do site FROID. Encerra quando a lista de defeitos verificáveis zera — não por autoavaliação.
---

# Revisão dos descritivos de serviço

Revise os textos e a substância dos descritivos de serviço do site. Onde houver como
melhorar o fluxo ou deixar mais claros os procedimentos, **execute** — não se limite a
apontar. Revise a gramática, com atenção à concordância verbal.

Se um argumento foi passado, restrinja a rodada àquela página. Caso contrário, percorra o
escopo abaixo.

## Escopo

**Editável** — descritivos de serviço em `froid-site/`:
`index`, `empresas`, `profissionais`, `precos`, `como-funciona-nr1`, `diagnostico-nr1`,
`proposta-nr1`, `froid-explica`, `froid-explica-nr1`, `iso-45003`, `ciencia`,
`demonstracao`, `faq`, `glossario`, `seguranca`, `etica`.

`seguranca` e `etica` são páginas descritivas de arquitetura, não instrumentos jurídicos —
e é nelas que vivem as afirmações sobre criptografia, isolamento e piso de coorte, que são
as mais propensas a erro. Entram no escopo editável por isso.

**Somente relatar, nunca editar:** `termos` e `privacidade`. São textos que o cliente
aceita e cujo aceite é provado por impressão digital; alterá-los aqui criaria divergência
entre o texto publicado e o texto aceito.

**Fora do escopo:** `froid-dashboard/` e `froid-server/`.

**Espelhos `en/`, `es/`, `fr/`:** entre neles apenas quando a divergência for **não
intencional**. Várias divergências são deliberadas — a página internacional abre pela ISO
45003 e não carrega o detalhe da NR-1, de propósito. Na dúvida sobre se a divergência é
intencional, pergunte; não "corrija".

## A regra que governa tudo

**Afirmação nova exige origem declarada.** Ao acrescentar qualquer conteúdo sobre o que o
produto faz, aponte a origem: o código, um documento em `docs/normas/`, ou uma confirmação
explícita do Fábio. Se não houver origem, o item **não vai para a página** — vira pergunta
no relatório da rodada.

Isto vale para números e igualmente para capacidades. Escrever "o FROID faz X" sem ter
aberto o código que faz X é o defeito mais caro que este site pode conter, e já aconteceu
neste repositório: uma tela existia e a página descrevia outra coisa.

## Rotina de cada rodada

1. Leia `docs/revisao-servicos-log.md` — crie na primeira rodada — para saber o que já foi
   revisado e o que ficou aberto. Não refaça trabalho pronto.
2. Escolha o próximo trecho do escopo e **leia o texto inteiro antes de mexer**.
3. Aplique as correções: cirúrgicas, no lugar. Nada de reescrever a página.
4. Rode a verificação (abaixo). Se acusar falha, corrija antes de seguir.
5. Commite a rodada, com mensagem dizendo o que mudou e por quê.
6. Atualize o log: página, o que mudou, defeitos fechados, defeitos abertos.

Commite por rodada. Um loop de muitas rodadas sem ponto de retorno acumula alterações em
dezenas de arquivos sem nenhum lugar seguro para voltar, e impede revisão incremental.

## Verificação após cada rodada

Tudo abaixo é checável por máquina. Rode e cole o resultado no log.

- **Encoding:** nenhum `Ã§`, `Ã£`, `â€` nas páginas tocadas.
- **Tags:** abertura e fechamento balanceados.
- **Âncoras:** todo `href="#x"` tem `id="x"` na página; todo `href="pagina.html#x"` tem
  `id="x"` naquela página.
- **Menu suspenso:** toda âncora de `NAV_SECOES`, em `site-assets/script.js`, existe na
  página correspondente. Este defeito **não aparece** na validação de HTML, porque o menu
  só existe depois que o script roda.
- **Números espelhados:** piso de anonimato, margem de amostra, corte de censo e preços
  batem entre todas as páginas, `docs/comercial/` e o código. Divergência é achado, e o
  certo é o da fonte — nunca o mais bonito.
- **Nomenclatura:** nenhuma ocorrência de nome aposentado. Vigente: **FROID Psique**
  (clínico), **FROID Psicossocial** (corporativo), **FROID Explica** e **FROID Explica
  NR-1**. "FROID Compliance" e "FROID NR-1" foram aposentados como nome de produto.
- **Fronteira clínica:** nenhum texto sugere que o empregador lê resposta individual.

## Os defeitos, e o critério de parada

Mantenha em `docs/revisao-servicos-log.md` uma **lista de defeitos verificáveis** — cada um
com página, descrição e como confirmar que foi resolvido.

**A rodada encerra quando essa lista zera**, e não por autoavaliação. Não se atribua nota:
quem produz o trabalho e dá a nota que decide quando parar não está medindo nada. A lista
é auditável pelo Fábio; a nota não seria.

Um defeito só sai da lista quando a verificação correspondente passa. Se a rodada não
conseguir fechar um item, ele permanece aberto no log com a razão.

### Classes de defeito que valem a busca

Em ordem de dano, e a primeira é a que nenhuma rubrica de redação captura:

1. **Falsidade ou exagero.** Afirmação que não se sustenta contra a fonte. Um texto pode
   ser claro, consistente, gramatical e completo — e estar errado. Já houve exemplo
   publicado neste site: "ausência de documentação equivale a presunção desfavorável",
   juridicamente falso, corrigido em 31/08/2026.
2. **Promessa que o produto não cumpre**, inclusive por omissão de ressalva.
3. **Divergência entre páginas** — número, nome, sequência ou promessa.
4. **Procedimento obscuro** — o leitor não sabe o que acontece, em que ordem, nem o que se
   espera dele.
5. **Lacuna de completude** — falta ao descritivo algo que o leitor precisa para decidir.
6. **Erro gramatical**, com atenção à concordância verbal.
7. **Fluxo** — ordem, transição, repetição.

## Convenções do repositório

- **`froid-site` é bind mount:** entra com `git pull`, sem rebuild.
- **Siglas:** expansão na primeira aparição, glossário ao pé.
- **Editar por script Python** com `io.open(..., encoding="utf-8")`. Heredoc de bash
  quebra com conteúdo grande e corrompe acentuação.
- **Alternância de fundo:** seções `block` e `block soft` alternam. Inserir ou remover
  seção exige recalcular a sequência inteira.
- **Índice e menu acompanham a estrutura.** Mexeu em seção, atualize o `#indice` da página
  e o `NAV_SECOES` — os dois apontam para âncoras e quebram em silêncio.
