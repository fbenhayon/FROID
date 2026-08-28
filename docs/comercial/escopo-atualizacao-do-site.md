# Atualização do site — escopo levantado em 27/08/2026

Escrito no fim de uma sessão longa, para que a próxima comece com um plano em
vez de uma descoberta. **Nada aqui foi executado.**

Por que não executei na hora: a alteração é grande, o site é a primeira coisa
que um cliente abre, e ela seria publicada sem ninguém acordado para revisar —
horas antes de uma reunião de fechamento. O risco de publicar às cegas é maior
do que o ganho de adiantar.

---

## O que mudou no produto e o site ainda não conta

### NR-1 — telas que passaram a existir

Todas construídas em 26 e 27/08/2026, e nenhuma aparece em `empresas.html` nem
em `como-funciona-nr1.html`:

| Tela | O que ela é |
|---|---|
| Campanha e convites | criar campanha, abrir e encerrar a coleta, emitir e reemitir convites |
| Inventário | o documento gerado, na tela e imprimível em A4 |
| FROID Explica NR-1 | 48 respostas curadas + pergunta aberta sobre acervo de 661 trechos |
| Plano de ação | as medidas, com estabelecimento identificado |
| Comprovante de aceite | prova de qual texto foi aceito, por quem e quando |

### NR-1 — argumentos que o site não usa

- **O recorte declarado insuficiente.** É a tese central do produto — “suprimir
  é ocultar; declarar insuficiente é documentar” — e o site fala pouco dela.
- **A prova de eficácia com incerteza declarada.** O site menciona; não mostra.
  O piloto produz números reais para ilustrar (`d=+0,60 ±0,60` → sem mudança).
- **O FROID Explica NR-1** como parte da entrega, e não como brinde.
- **A fronteira demonstrável ao vivo** — entrar como empresa e ver o painel
  clínico recusar. Vale um bloco próprio; é o argumento que nenhum concorrente
  reproduz.
- **O que o RH precisa fazer**, que hoje só existe nas notas técnicas: nunca
  enviar nomes, apagar o arquivo de links depois de distribuir, e o convite ser
  de uso único.

### FROID Psique — o pedido explícito do Fábio

Relatórios do paciente e do profissional. **Não levantei o estado atual dessas
telas nesta sessão** — o trabalho todo foi no módulo NR-1. A próxima sessão
precisa começar por aí: abrir `SessionReport`, `PatientPortalPage` e
`Dashboard`, ver o que existe hoje, e só então decidir o que o site deve
mostrar. Não confiar nesta lista para essa parte.

---

## Ordem sugerida

1. **Levantar** o estado real das telas do Psique antes de escrever qualquer
   copy sobre elas. O padrão deste repositório é que a peça já exista e ninguém
   a esteja chamando — presumir custa mais caro que grepar.
2. **NR-1 primeiro**, porque é o que está fresco e é o que tem cliente na mesa.
3. **Psique depois**, com o levantamento em mãos.

## Armadilhas conhecidas deste repositório

- **`froid-site` é bind mount**: entra com `git pull`, sem rebuild. O painel
  (`froid-dashboard`) exige `docker compose build froid-frontend`.
- **Espelhos de número.** Piso, margem e preço aparecem em vários arquivos.
  Antes de alterar qualquer número no site, rodar
  `tests/test_nr1_espelhos_do_portao.py` e conferir `proposta-nr1.html` e
  `tools/simulador_nr1.py`, que já divergiram antes.
- **Encoding.** Edição malfeita de HTML corrompe UTF-8. Conferir mojibake e
  balanceamento de tags depois de cada alteração.
- **Siglas.** O site adota expansão na primeira aparição mais glossário ao pé.
  Manter em qualquer texto novo.
- **Preço.** A tabela vigente é a original — base de R$ 1.200/mês por unidade
  mais faixas de R$ 9 / 7 / 5 / 3. Foi alterada e revertida em 27/08; não
  ressuscitar a versão intermediária.
