# Revisão do site — 07/10/2026 — o que foi enviado, o que era, o que está no ar

Pedido do dono: "os endereços html estão desajustados; siga as novas
instruções e conteúdo e faça o merge com as páginas atuais; preserve tabelas e
mecanismos de apuração de valores". Esta é a análise que antecede a decisão.

Três versões comparadas, página a página:

- **enviado** — as 27 páginas entregues em 06/10 (e reenviadas em 07/10, idênticas);
- **original** — as 22 páginas que estavam no ar até 06/10 (commit 5271ccd7);
- **no ar** — o que está publicado agora (commit f8cf39a1): enviado + componentes devolvidos.

## 1. Endereços desajustados (achados concretos)

| # | Onde | O que está desajustado | Estado |
|---|---|---|---|
| 1 | `precos-v2.html` | As páginas enviadas apontam para `precos-v2.html` (menu, demonstração, FAQ, profissionais, contato). No ar, esses links foram trocados para `precos.html`, que é a página pública de preços. Mas `precos-v2.html` **continua existindo no servidor como a página antiga, sem header e sem rodapé** (nos quatro idiomas, `noindex`). Quem digita o endereço vê uma página solta. Nada mais a referencia; só o teste `test_psique_phase5` exige que exista. | **a corrigir** |
| 2 | Header | A navegação enviada tem **"FROID" → página inicial** como primeiro link e **"Contato"** como último. No header do site, o espaço da marca é o logo oculto (link sem texto visível): **não há como voltar à página inicial pelo header**, e não há "Contato" (só no rodapé e nos botões das páginas). | **a decidir** |
| 3 | `sobre-contato.html` | O cartão `#psique` já tem o formulário real (pedido de 07/10). Os cartões `#nr1`, `#data-froid` e `#dados` continuam com botão `mailto:` e link secundário. Treze páginas apontam para `#psique`, onze para `#nr1`, três para `#dados`, duas para `#data-froid`. | **a decidir** |
| 4 | `diagnostico-nr1.html` | A seção enviada "Participação e privacidade são critérios distintos" dizia "esta página não gera um número de aprovação automático". Ao devolver a calculadora (pedido de 06/10), a frase ficou falsa e a seção saiu. É a única seção enviada que não está no ar. | **a devolver, com a frase ajustada** |
| 5 | Links `/app/#/...` | Enviado: relativos. No ar: absolutos (`https://www.froid.com.br/app/#/...`), padrão do site. Funcionam igual. | ok |

## 2. O que está no ar além do enviado (preservar)

Devolvido das páginas originais a pedido (06/10): calculadora de piso e "Por que
existe um piso" (prontidão); "Quanto custa" com faixas e simulador que consulta o
motor (empresas); faixas e simulação (proposta); tabela de perigos do Guia MTE e
seção de anonimato (como funciona NR-1); números do corte e capturas do
aplicativo (demonstração); mapa FACS em miniatura (mapas da face); capturas em
índice, profissionais, Explica e tecnologia; blocos vivos de preço (preços).

Acrescentado por exigência de teste ou de código: formulário `/api/contato`
(contato); `k ≥ 7` (glossário); Finlândia, SHA-256 e "não grava a sessão"
(privacidade, segurança, termos); "não conduz avaliação em campo", "Campanhas
ilimitadas." e CNPJ (empresas, proposta); "AWS/Hetzner" corrigido para a
Finlândia (segurança); a "pré-checagem de câmera", que não existe, reescrita
(como funciona clínico, profissionais).

## 3. O que era original e NÃO está no ar

Seções inteiras das páginas de até 06/10 que a versão enviada não tem. Entre
elas há tabelas e mecanismos que o pedido de 07/10 manda preservar.

| Página | Seções originais ausentes | Tabelas/mecanismos entre elas |
|---|---|---|
| `empresas` | 13 de 14: O que mudou na norma; Três documentos; O custo da omissão; Seis erros que geram passivo; A AEP psicossocial; O ciclo operado pela contratante; Provar que a medida funcionou; Quando o dado não basta; Gestão tradicional × FROID; Cinco perguntas ao fornecedor; O que é e o que não é; Comece por um estabelecimento. Em en/es/fr a página original era mais curta: 6 seções próprias (dever do empregador; dois portões; provar eficácia; dado insuficiente; fronteira; o que é e não é), também ausentes | **tabela comparativa** Gestão tradicional × FROID (pt e traduções) |
| `proposta-nr1` | 7 de 8: O que está sendo contratado; Fases; O que a contratante precisa fornecer; Por que este procedimento; Proteção de dados; Limites do serviço; Aceite | tabela de implantação (campos em branco, faixas de referência) |
| `como-funciona-nr1` | 5 de 7: As nove etapas; Comprovação de Gestão Disciplinar; O que muda em cada empresa; E se a segunda avaliação reprovar; A sua empresa tem tamanho | **cadeia de SHA-256 do dossiê** (mecanismo), formatos PDF/JSON |
| `iso-45003` | 7 de 7: todas (leitura da norma, critério do MTE, dever documental, ISO 45001) | — |
| `froid-explica-nr1` | 6 de 6: duas camadas; oito temas; o que o RH pergunta; o que está indexado; o que não é | — |
| `demonstracao` | 12 de 12: o percurso completo (conta, convite, sala, calibração, tela, relatório, documento do paciente, Data-Froid) | — (números do corte já devolvidos) |
| `profissionais` | 7 de 7: antes/durante/depois; controle financeiro; relatórios; equipe; o que é e não é | — |
| `froid-explica` | 7 de 7: sessão real; dois cérebros; conduta; perguntas; prompts pessoais; Data-Froid | — |
| `index` | 8 de 8: manifesto; o que acompanha a sessão; Data-Froid; rotina clínica; Explica; Portal do Paciente; ciência × metodologia; próximo passo | — |
| `tecnologia` | 7 de 7: calibração; extração acústica; FACS; 12 Zonas; acervo; IPM/IDM; estabilização | descrevem o **motor anterior** (12 zonas, dissonância) |
| `ciencia` | 9 de 9: evidências por tema; Markov facial; micro-tremor; 12 zonas; bibliografia | idem |
| `mapas-faciais` | 5 de 5: dois mapas; o que cada AU significa; como se combinam; do rosto à leitura; o que não afirmam | **tabelas de AU e de combinações** do motor anterior |
| `etica` | 7 de 7: cinco pilares; modelo de TCLE; kit de conformidade | modelo de TCLE |
| `seguranca` | 3 de 3: proteção; caminho da sessão; LGPD | — |
| `faq`, `sobre-contato` | texto anterior (15 perguntas; "Fale com o time") | — |

**Atenção:** as seções originais de `tecnologia`, `ciencia`, `mapas-faciais` e
parte de `demonstracao`/`index` descrevem o motor facial de 12 zonas com
dissonância, retirado em 06/10 (commit 1a6867b7). Devolvê-las como estavam
reintroduziria afirmações que o código não sustenta mais; cada uma precisaria
ser reescrita contra o código. As seções do NR-1 (`empresas`, `proposta`,
`como-funciona-nr1`, `iso-45003`, `froid-explica-nr1`) não dependem do motor e
continuam verificáveis contra o código e as normas.

## 4. Decisão do dono e execução (07/10/2026)

Base escolhida: **as páginas enviadas continuam a base; voltam as seções
originais das cinco páginas do NR-1**, nos quatro idiomas, copiadas do commit
5271ccd7 (nada redigitado). Os quatro endereços da tabela 1 foram corrigidos.

| O que | Como ficou |
|---|---|
| `empresas` | pt: 11 seções originais (retrato legal → cinco perguntas ao fornecedor antes de "Quanto custa"; "limites e responsabilidade" depois). en/es/fr: as 6 seções da página internacional original (dever do empregador, dois portões, prova de eficácia, dado insuficiente, fronteira, o que é e não é). "Compliance FROID" e "FROID NR-1/ISO-45003" viraram "FROID NR-1". |
| `proposta-nr1` | 7 seções originais convertidas da folha clara para o template escuro (`.destaque` em três cores, `.tabela-doc`, `.assinatura`). A frase da janela de orientação passou ao pretérito nos quatro idiomas (fechou em 24/08/2026). Tabelas "Implantação e ciclo" e "AEP com inventário" **não** voltaram (decisão de 06/10). A linha do CNPJ voltou a viver só no Aceite. |
| `como-funciona-nr1` | As nove etapas, "O que é igual em toda empresa", "E se a segunda avaliação reprovar", "A sua empresa tem tamanho"; em pt também a "Comprovação de Gestão Disciplinar" (cadeia SHA-256, botão para `/app/#/registrar`). |
| `iso-45003`, `froid-explica-nr1` | Todas as seções originais, nos quatro idiomas. |
| `diagnostico-nr1` | "Participação e privacidade são critérios distintos" devolvida, com a frase falsa trocada por: a calculadora estima com os pisos espelhados do servidor; a liberação real é decidida no banco. |
| `precos-v2.html` | Apagada nos quatro idiomas; `test_psique_phase5` passou a guardar `precos.html`. |
| Header | Marca com texto "FROID" visível (link para a inicial) e "Contato" como último link solto, nos quatro idiomas; continua em uma linha a 1280 e 1366. |
| `sobre-contato` | Formulário real nos quatro cartões (pt tinha só o do Psique), cada um com `data-origem` próprio; `enviarContato` das traduções lê o formulário que disparou o evento, como em pt. Saiu a frase "os botões acima abrem seu e-mail". |
| CSS | O `<style>` das páginas originais foi para `paginas.css` (v3); `script.js` v21 com o `NAV_SECOES` regerado. |

Verificação: `verificar-site.py` 108 páginas, 0 falhas; `gerar-header-do-site.py
--conferir` ok; 178 testes do site passando; `checar-telas-do-site.mjs` 81
medições pt e 39 em traduções, 0 com problema.

**Ficou para o dono decidir:** `como-funciona-nr1` em pt agora traz as sete
etapas da versão enviada *e* as nove etapas originais; `proposta-nr1` traz
"Etapas que a proposta pode contemplar" *e* "Fases". São duas contagens para o
mesmo percurso na mesma página.
