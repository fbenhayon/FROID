# FROID - Estabilizacao Clinica da Tela

Area: Notas tecnicas FROID; IPM/IDM; Bioacustica; Interface clinica.

Uso no FROID Explica: documento proprietario citavel para perguntas sobre cadencia de atualizacao visual, janelas clinicas, botao "Atualizar agora" e diferenca entre processamento bruto e apresentacao ao profissional.

## Definicao

A Estabilizacao Clinica da Tela e uma camada proprietaria do FROID que separa o processamento tecnico bruto da apresentacao visual ao profissional.

O processamento bruto permanece em alta frequencia para preservar acuracia temporal, capturar picos, manter baseline e registrar eventos transitorios. A tela do profissional, entretanto, pode operar em uma janela clinica estabilizada para reduzir ruido visual e permitir interpretacao, consulta ao FROID Explica e tomada de decisao durante a sessao.

## Modos de apresentacao

- Tempo real: sem congelamento visual. Graficos e indicadores acompanham a cadencia tecnica disponivel.
- 1 minuto: janela clinica leve para supervisao rapida.
- 3 minutos: janela dinamica para sessoes com maior variabilidade.
- 5 minutos: padrao recomendado para leitura clinica, preservando estabilidade sem atrasar excessivamente alertas relevantes.
- 7 minutos: janela reflexiva para sessoes mais lentas ou exploratorias.

## Microjanelas tecnicas

A camada visual estabilizada utiliza microjanelas tecnicas de 1 minuto. Cada microjanela consolida os sinais disponiveis naquele minuto, incluindo IPM, IDM, zonas, tom emocional, biomarcadores acusticos, bandas espectrais, sub-harmonicos, DNA bioacustico e dissonancias detectadas.

## Como a janela padrao de 5 minutos se comporta

Na janela clinica de 5 minutos, o valor apresentado ao profissional e uma media ponderada das ultimas cinco microjanelas de 1 minuto, e nao a leitura do instante.

O que importa clinicamente e o formato da ponderacao: o minuto atual pesa mais que os anteriores, e o peso decai a cada minuto que se afasta. Isso produz uma tela que nao oscila a cada respiracao, mas que ainda se move quando o estado do paciente muda de fato. Os valores exatos dos pesos sao parametro proprietario e nao constam desta nota; o que o profissional precisa saber para ler a tela e a direcao do decaimento, nao o numero.

## Regras por metrica

- IPM: media ponderada temporal das microjanelas.
- IDM: media ponderada temporal preservando sinal e intensidade.
- Zonas FROID: zona dominante por intensidade ponderada e persistencia relativa.
- Dissonancias: exibidas quando persistem acima do limiar em janela relevante; alertas criticos podem romper a estabilizacao visual.
- MFCC7, MFCC9, ZCR, Jitter, Shimmer e sub-harmonicos: media ponderada temporal com manutencao interna dos picos no historico bruto.
- Tom emocional: predominancia temporal ponderada, com preferencia ao estado mais recente quando houver empate.
- Palavras por minuto: calculadas sobre a janela clinica exibida.

## Botao Atualizar Agora

O botao "Atualizar agora" força a geracao imediata de uma nova janela clinica sem alterar os cortes formais da sessao. Ele permite ao profissional atualizar a tela quando desejar investigar uma mudanca percebida, consultar o FROID Explica ou comparar a tela estabilizada com o momento clinico atual.

## Alertas criticos

A estabilizacao visual nao deve impedir a exibicao de eventos clinicamente relevantes. Quando o FROID detecta dissonancia forte, alerta bruto relevante ou sinal multimodal acima do limiar configurado, a janela clinica pode ser atualizada antes do prazo programado.

## Relacao com cortes da sessao

A Estabilizacao Clinica da Tela nao altera os cortes formais da sessao. Os cortes de relatorio e resumo seguem sua cadencia propria e preservam a arquitetura longitudinal da consulta. A estabilizacao atua somente na cadencia de apresentacao em tela.

## Racional clinico

A atualizacao visual excessivamente curta pode prejudicar a capacidade do profissional de interpretar graficos, examinar indicadores, consultar o FROID Explica e decidir intervenções. A estabilizacao clinica reduz ruido operacional sem reduzir a acuracia do processamento bruto.
