# FROID Explica — Fase 5: a referencia populacional do Data-FROID

Desenho de 26/10/2026, lido contra `main` (`ef54c247`). Fases 1 a 4 em
producao; a revisao pre-fase 5 (grupos 1 a 3) publicada no mesmo dia.

## O problema

O Explica sabe comparar um paciente com ele mesmo (cortes, sessoes) e com o
que a pessoa ve na clinica. Nao sabia situar um valor frente ao conjunto de
sessoes do FROID: "um IPM de 62 e alto?" so tinha resposta pela rota de
analytics, por palavra-gatilho, com SQL escrito pelo modelo e narrado por um
segundo modelo — fora do laco clinico e sem o contexto da sessao aberta.

## O principio que nao se negocia

**Agregado, anonimo e com piso.** A referencia le o acervo anonimo
(`anonymous_sessions`, `anonymous_session_cuts`), nunca o acervo de relatorios.
Abaixo do piso de coorte (`FROID_ANALYTICS_MIN_K`, 7 em producao) nenhum
numero sai, nem o parcial. E nao e norma clinica: a distribuicao e das sessoes
que passaram pelo FROID, e a instrucao obriga o assistente a dizer isso e a
citar o numero de sessoes.

## Decisoes de desenho

| Decisao | Por que |
|---|---|
| Lista fechada de medidas, SQL parametrizado no servidor (`data_froid_referencia.py`) | O modelo escolhe medida e filtros; nunca escreve SQL. A rota de analytics continua existindo para pergunta agregada livre, com a arvore do DuckDB vigiando |
| Medida acustica so a partir de `VERSOES_SEM_ZERO_FALSO` (v4, v5) | Ate a v3 ausencia era gravada como 0.0 e puxava a media; a resposta declara as versoes consideradas |
| NULL fora da conta, com `n_apurado` ao lado de `sessoes` | `AVG` ignora NULL em silencio; o leitor precisa ver sobre quanto a media foi feita |
| Posicao do valor do paciente calculada pelo servidor (`AVG(CASE WHEN col < valor)`) | Regra da casa: o assistente nao calcula percentual de cabeca |
| Filtros so por `age_bucket`, `gender`, `session_modality`, por parametro | Categorias do acervo; nada de texto livre e nada interpolado |
| Nenhuma coluna de texto na lista | Tema, resumo e sintese nao passam por aqui; a busca por tema (fase 4 do acervo) continua fora ate o v5 crescer |
| As sessoes do proprio profissional entram no agregado | E agregado com piso; a regra "nunca sessao do proprio profissional" do acervo vale para devolver TEXTO, nao para contar |

## A ferramenta

| Ferramenta | Entrada | Le de | Devolve |
|---|---|---|---|
| `referencia_populacional` | medida (enum), valor_do_paciente, age_bucket, gender, session_modality | acervo anonimo (DuckDB, somente leitura) | sessoes distintas, registros apurados, media, mediana, quartis, filtros, versoes, posicao do valor |

Injecao: `main._referencia_populacional_do_data_froid` entra no `Acervo` quando
o arquivo do acervo existe; sem ele, a ferramenta declara "nao disponivel neste
servidor" e o modelo responde sem referencia.

## Estado do acervo em producao (26/10/2026)

51 sessoes e 145 cortes; a maioria em v3 (zero falso) — as medidas acusticas
por sessao tem coorte pequena ate o acervo crescer, e a ferramenta vai dizer
"coorte insuficiente" com frequencia. Isso e o acervo, nao a ferramenta: a
resposta certa abaixo do piso e a declaracao, nunca um numero.

## Provas

`tests/test_data_froid_referencia.py` (DuckDB em memoria): piso sem vazar n
parcial; piso por sessao distinta e nao por corte; v3 fora das acusticas e
dentro das nao acusticas; NULL fora com n_apurado; filtro declarado e filtro
fora da lista ignorado; posicao do valor; medida fora da lista recusada;
rotulos dos cortes iguais aos do painel. `tests/test_explica_ferramentas.py`:
a ferramenta no esquema, o executor passando a entrada, a ausencia declarada.

## O que NAO entra

- Busca por tema no acervo (fase 4 do plano do Data-FROID): sem corpus v5.
- Trocar a rota de analytics: segue por palavra, com a mesma protecao.
- Traducoes do site (en/es/fr): seguem o texto anterior.
