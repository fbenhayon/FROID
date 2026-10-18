# FROID Explica — Fase 4: ferramentas com acesso no servidor

Desenho de 18/10/2026, lido contra `main` (`9749d0c3`). Fases 1 a 3 em
producao: cortes compactos no prompt, Claude primeiro, contrato por modo.

## O problema

O navegador monta o contexto e o manda inteiro a cada pergunta. Funciona para
UMA sessao. Para "as sessoes deste paciente", "meus pacientes" ou "a clinica",
o servidor so sabia injetar a carteira quando a pergunta tinha uma palavra
gatilho (`_is_comparative_question`: "compar", "evolu", "historico"...), e o
que injetava era um resumo fixo. A pergunta "quantos pacientes cada
profissional atende" nao tinha caminho nenhum.

## O principio que nao se negocia

**O Explica nao ve mais que a tela.** Toda ferramenta le do mesmo conjunto que
`_accessible_session_reports` devolve ao painel — posse, atribuicao a membro e
visibilidade de clinica decidida pelo gestor (`main.py:16551`). Nenhuma
ferramenta abre caminho novo de acesso; o que o gestor nao ve no painel, o
Explica nao agrega. Nome de paciente nao entra no prompt (regra ja existente
em `_format_session_context`); as ferramentas trabalham com identificadores.

## Decisoes do dono

| Decisao | Estado |
|---|---|
| Agregado de clinica = contagens e medias sobre as sessoes que o solicitante JA pode ver; nunca transcricao de sessao de outro profissional | ASSUMIDO em 18/10/2026 por ser o que o RLS atual permite; nao amplia acesso. Pode ser restringido depois |
| "Grupo" de profissionais como entidade | NAO EXISTE no cadastro (ha atribuicao de relatorio a membro e visibilidade de clinica). Fica fora ate decisao |
| Caminho duplo temporario: ferramentas so no caminho Claude; Gemini/OpenAI seguem com o contexto que o navegador manda | ASSUMIDO — os outros motores nao entram no laco; some quando o Claude for o unico |

## As ferramentas (`froid-server/explica_ferramentas.py`)

| Ferramenta | Entrada | Le de | Devolve |
|---|---|---|---|
| `cortes_da_sessao` | session_id | relatorio arquivado acessivel | o mesmo bloco de cortes da fase 1, montado no servidor |
| `sessoes_do_paciente` | patient_id | relatorios acessiveis daquele paciente | uma linha por sessao (carteira), com desvio contra a linha de base |
| `pacientes_do_profissional` | — | relatorios acessiveis | por paciente: sessoes, primeira e ultima data, IPM e P/MIN medios |
| `agregado_da_clinica` | por = profissional / clinica | relatorios acessiveis | por profissional ou total: pacientes, sessoes, medias com n |
| `trecho_da_transcricao` | session_id, inicio_s, fim_s | transcricao da sessao acessivel, decifrada so quando pedida | linhas com [mm:ss] no intervalo, teto declarado |

Esquemas estritos (`strict: true`, `additionalProperties: false`). Erro de
ferramenta volta como `tool_result` com `is_error`, nunca como texto que
parece dado. Cada chamada fica no log (nome e chaves da entrada, sem conteudo).

## O laco

Manual, em `_claude_responde` (`main.py`): enquanto `stop_reason` for
`tool_use`, executa as chamadas do turno, devolve todos os resultados numa so
mensagem, e segue. Teto de 6 turnos de ferramenta, declarado no log. Sem
`tool_choice` forcado (a API devolve 400 nesta familia).

A tabela compacta por corte ganha um produtor no servidor (`ROTULOS_DO_SNAPSHOT`
em `explica_ferramentas`), espelho do produtor do painel; um teste confronta
os dois pela lista (rotulo, campo, casas) lida do arquivo TypeScript, como ja
se faz entre o painel e o glossario.

## O que NAO entra

- Data-FROID como ferramenta (fase 5): a rota de analytics segue por palavra.
- Trocar o que o navegador manda: continua mandando o contexto, porque os
  motores de contingencia dependem dele.
