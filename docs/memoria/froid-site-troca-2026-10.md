---
name: froid-site-troca-2026-10
description: Em 06/10/2026 as 27 paginas do froid-site foram trocadas pela versao nova e traduzidas; em 07/10 as secoes originais do NR-1 voltaram por cima (fonte: commit 5271ccd7) e os enderecos foram corrigidos; o que a revisao ensinou sobre 'substituir' um site
metadata:
  node_type: memory
  type: project
  originSessionId: 6f5b85ec-863e-4276-b832-e997b2e18a88
  modified: 2026-10-06T19:49:40.029Z
---

Em 06/10/2026 o Fabio entregou 27 paginas novas (HTML minimo, menu proprio) e
pediu para substituir as existentes, reaproveitando o template. Montei as 28
paginas pt-BR (27 + `precos.html`) com o chrome do site: header do gerador,
hero, blocos alternados, footer, `style.css` + `refinement.css` + um
`paginas.css` novo so com o que nao existia (acordeao de FAQ, checklist,
analogia, coluna de prosa). O script de montagem viveu no scratchpad e NAO esta
no repositorio: daqui em diante edita-se o HTML direto, como antes.

**Arquitetura nova (pt-BR):** `index.html` virou institucional (dois produtos);
`profissionais.html` e a visao geral do Psique e `empresas.html` a do NR-1.
Seis paginas existem SO em pt-BR: `como-funciona-clinico`, `data-froid`,
`menu` (mapa do site, "Explorar" no header), `faq-nr1`, `glossario-nr1`,
`seguranca-nr1`. O gerador so emite pill/hreflang para traducao que existe.

**Preco:** `precos.html` continua sendo a pagina publica (rota `/precos`,
`conferir-deploy.py`, testes); recebeu o texto novo do modelo V2 mais os blocos
vivos de preco do backend (trial, pacotes, calculadora da licenca). Todos os
links que as paginas novas faziam para `precos-v2.html` apontam para ela;
`precos-v2.html` segue como copia noindex sem header.

**O que a versao nova tirou do pt-BR de proposito** (e os testes passaram a
guardar a decisao nova, com docstring datada): a calculadora de piso de
`diagnostico-nr1` (`test_nr1_espelhos_do_portao`), a tabela de faixas e a
simulacao de preco do NR-1 em `empresas`/`proposta-nr1`
(`test_precos_nr1_espelhados`), a frase "a partir de 15 trabalhadores"
(`test_piso_na_prosa_comercial`), os numeros do corte na demonstracao
(`test_percurso_do_psique` passou a varrer POR FORMA todas as paginas pt).
Tambem sairam: a citacao-manifesto da index, as capturas de tela, os mapas
FACS em imagem, a tabela de perigos do Guia MTE, o modelo de TCLE da etica.

**O que acrescentei as paginas novas, com origem:** secao
`#anonimato-das-respostas` em como-funciona-nr1 (teste amarra ao codigo);
"nao conduz avaliacao em campo" e "Campanhas ilimitadas." em empresas e
proposta (determinacao de 12/09); CNPJ do fornecedor na proposta; "k >= 7" no
glossario (`FROID_ANALYTICS_MIN_K`); "60 segundos de calibracao" em
tecnologia; "na Finlandia" e SHA-256 em privacidade/seguranca/termos;
formulario de contato real (`/api/contato`) no lugar do "nenhum formulario";
e troquei "AWS/Hetzner" (nao ha AWS em lugar nenhum) e a "pre-checagem de
camera" (nao existe tela previa).

**Why:** o site e lido por cliente; cada numero copiado la ja divergiu uma vez
(piso 50 x 15). A versao nova resolveu isso nao publicando numero — e os
testes que exigiam os numeros precisavam acompanhar a decisao, nao vence-la.

**How to apply:** as traducoes en/es/fr continuam com o CONTEUDO anterior
(precos, calculadora, mapas); o gerador carrega `NAV_SECOES_TRADUCOES` para
nao empobrecer os cabecalhos delas — ao traduzir as paginas novas, apagar esse
mapa. Verificacao da rodada: `python docs/verificar-site.py` (agora valida
JSON-LD como JSON), `python tools/gerar-header-do-site.py --conferir`, os 15
testes que leem o site, e `node tools/checar-telas-do-site.mjs` (Chrome
headless por CDP: rolagem horizontal, borda, header numa linha a 1280/1366).
Ver [[froid-site-architecture]], [[froid-espelhos-de-numero]],
[[froid-site-afirma-o-que-o-painel-nao-faz]].

**Atualizacao, mesmo dia (pedido do Fabio):** a calculadora de piso, as faixas
e o simulador/simulacao do NR-1, a tabela de perigos do MTE, os numeros do
corte, os mapas FACS (miniatura + lightbox) e as imagens do produto VOLTARAM,
copiados das paginas antigas; os quatro testes afrouxados voltaram a forma
original (fase 1 = commit 8ef9b632). As 27 paginas foram traduzidas para
en/es/fr com a arquitetura nova, e `NAV_SECOES_TRADUCOES` saiu do gerador.
Moeda: mesmo valor em todos os idiomas, sem conversao, simbolo R$ (e a moeda
cobrada). Fase 2 (traducoes + ferramentas + docs) ficou sem commit, aguardando
o Fabio.

**Revisao de 07/10/2026 (Fabio reenviou as 27 paginas: "fiz uma grande
confusao na solicitacao inicial").** O pedido de "substituir" tinha apagado
conteudo que ele queria: as secoes longas do NR-1. Decisao dele: paginas
enviadas continuam a base; as secoes originais de `empresas`, `proposta-nr1`,
`como-funciona-nr1`, `iso-45003` e `froid-explica-nr1` voltam por cima, nos 4
idiomas, COPIADAS de `git show 5271ccd7:froid-site/...` (nunca redigitadas).
As traducoes originais de `empresas` tinham 6 secoes proprias (pagina
internacional mais curta), nao as 11 de pt — restaurar "o original" e por
idioma, nao por copia do pt. Enderecos: `precos-v2.html` apagada (4 idiomas),
"FROID" visivel + "Contato" no header, formulario nos 4 cartoes de contato,
secao de prontidao devolvida com a frase ajustada. O CSS das paginas originais
vive agora em `paginas.css` (v3). Fase 2 continua sem commit.

**Licao:** quando o dono manda "substituir" paginas inteiras, listar ANTES o
que sai (secao por secao) e perguntar — custou uma rodada inteira de revisao.
E ao devolver secoes originais, conferir se a pagina nova ja conta a mesma
historia com outros numeros: `como-funciona-nr1` ficou com 7 etapas novas e 9
originais na mesma pagina; devolvi a escolha ao Fabio em vez de decidir.
