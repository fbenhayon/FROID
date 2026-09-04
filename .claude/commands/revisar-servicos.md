---
description: Revisão minuciosa dos textos e da substância dos descritivos de serviço; só encerra com nota > 95
argument-hint: "[página ou área específica — opcional]"
---

# Revisão minuciosa dos serviços FROID

Faça agora uma revisão minuciosa nos textos e na nova substância dos nossos serviços.
Onde houver possibilidade de melhorar o fluxo e deixar mais claros os procedimentos e o
conteúdo dos descritivos, **execute** as atualizações necessárias — não se limite a apontar.
Se algo de relevância estiver faltando e melhorar o que já existe, acrescente. Revise o texto
buscando a concordância verbal correta.

Se `$ARGUMENTS` estiver preenchido, restrinja a rodada a essa página/área. Caso contrário,
percorra o escopo abaixo.

## Escopo

Descritivos de serviço em [froid-site/](froid-site/):
`index`, `empresas`, `profissionais`, `precos`, `como-funciona-nr1`, `diagnostico-nr1`,
`proposta-nr1`, `froid-explica`, `froid-explica-nr1`, `iso-45003`, `ciencia`,
`demonstracao`, `faq`, `glossario`.

Espelhos `en/`, `es/`, `fr/`: só entre neles quando o conteúdo divergir do português —
divergência de substância é defeito, diferença de idioma não é.

**Fora do escopo:** `froid-dashboard/`, `froid-server/`, e os textos jurídicos
(`termos`, `privacidade`, `seguranca`, `etica`) — nestes, reporte o que achar, não edite.

## Rotina de cada rodada

1. Leia `docs/revisao-servicos-log.md` (crie na primeira rodada) para saber o que já foi
   revisado e o que ficou pendente. Não refaça trabalho já feito.
2. Escolha o próximo trecho do escopo e leia o texto por inteiro antes de mexer.
3. Aplique as correções — cirúrgicas, no lugar; nada de reescrever a página toda.
4. Dê a nota (rubrica abaixo) e registre no log: página, o que mudou, nota, o que ficou aberto.

## Regras

- **Encoding:** os HTML são UTF-8. Depois de editar, confira que não apareceu mojibake
  (`Ã§`, `Ã£`, `â€"`). Se apareceu, desfaça e refaça a edição.
- **Números não se inventam:** pisos de coorte, preços, fórmulas e prazos têm fonte. Se um
  número aparece em mais de um lugar, todos têm de bater; divergência é achado, e o certo é
  o da fonte — não o mais bonito.
- **Nome do produto:** use a nomenclatura vigente (FROID Psicossocial, FROID Psique,
  FROID Explica NR-1). Nome antigo remanescente é defeito a corrigir.
- **A fronteira clínica:** nenhum texto pode sugerir que o empregador lê dado individual.
- Não faça `commit` nem `push` — deixe as mudanças na árvore de trabalho e relate.

## Rubrica (0 a 100)

| Critério | Peso |
|---|---|
| Clareza do procedimento — o leitor sabe o que acontece, em que ordem, e o que se espera dele | 25 |
| Consistência entre páginas — nomes, números, promessas e sequência batem | 25 |
| Correção gramatical, com atenção à concordância verbal | 20 |
| Completude — nada relevante falta ao descritivo | 20 |
| Fluxo de leitura — ordem, transições, ausência de repetição | 10 |

## Critério de parada

Só se dê por satisfeito quando a nota for **maior que 95**. Enquanto for 95 ou menos,
corrija o que puxou a nota para baixo e siga na próxima rodada. Ao ultrapassar 95, diga
explicitamente que o critério foi atingido e **encerre o loop**.
