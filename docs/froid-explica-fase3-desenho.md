# FROID Explica — Fase 3: um contrato por modo

Desenho de 18/10/2026, lido contra `main` (`1f258afd`). Fases 1 e 2 em
producao: os cortes chegam ao modelo numa secao propria do prompt, e o Claude
responde primeiro.

## O problema que sobrou

O contrato da resposta (`explica_clinico._CONTRATO`) foi escrito para a sessao
ao vivo: 200 palavras, prosa, sem lista, porque o profissional esta com o
paciente na frente. Na pagina de relatorio a mesma pessoa esta analisando
depois, e pediu "o valor por corte e o percentual de variacao" — oito linhas
que o contrato proibe de sair como tabela. O bloco de cortes manda enumerar;
o contrato manda nao listar. Duas instrucoes contrarias no mesmo prompt.

## Decisoes do dono

| Decisao | Data |
|---|---|
| Dado primeiro, tamanho depois: no modo de analise nao ha teto fixo de palavras, desde que haja resumo por corte | DECIDIDO em 15/10/2026 (mensagem "aumentar o numero de palavras... ate mesmo tornando ilimitado") |
| Sessao ao vivo continua curta (200 palavras) | mantida; a reclamacao de 07/09 ("ninguem le quatro telas com paciente na frente") continua valendo la |
| Teto de tokens do modo de analise: 4.000 nos motores sem raciocinio contado (Gemini/OpenAI); o caminho Claude ja tem 16.000 | derivado, nao decidido: 20 cortes x ~25 tokens por linha de tabela + ~1.200 palavras de sintese cabem em ~3.000; o resto e folga. Ajustavel por `FROID_EXPLICA_MAX_TOKENS_ANALISE` |

## O que entra

1. **Dois contratos** em `explica_clinico.py`: `_CONTRATO` (ao vivo, como esta)
   e `_CONTRATO_DE_ANALISE` (tabela em markdown primeiro, uma linha por corte
   ou sessao, com o desvio que o servidor calculou; depois os quatro
   movimentos em ate tres paragrafos). `instrucao(frase, modo=...)`.
2. **O modo e declarado pelo painel** (`explica_mode`: `ao_vivo` | `analise`),
   nao inferido. Sem declaracao, o servidor cai em `analise` se vierem
   cortes e em `ao_vivo` no resto — `modo_do_contexto` em `explica_clinico`.
3. **Teto por modo** em `main.py`: `_modo_e_teto(contexto)` devolve o modo e o
   `max_tokens`; `FROID_EXPLICA_MAX_TOKENS_ANALISE` tem linha no compose com o
   mesmo padrao do codigo (teste compara).
4. **O painel renderiza a tabela.** `AIInsights` mostrava o texto cru em
   `whitespace-pre-wrap`; uma tabela markdown sairia como barras verticais.
   `lib/resposta-do-explica.ts` separa texto e tabela; o componente desenha a
   tabela e tira os asteriscos de negrito do texto (o contrato ja os proibe).
5. **A sessao ao vivo manda os cortes ja fechados**, compactos, com o mesmo
   produtor do relatorio (`contextoDosCortes`), so quando existe corte
   fechado — sem corte fechado nao se inventa janela de dez minutos.

## O que NAO entra

- Ferramentas com acesso no servidor (fase 4) e Data-FROID (fase 5).
- Mudar o glossario ou o bloco de cortes: estao certos; o que estava errado
  era o contrato por cima deles.
