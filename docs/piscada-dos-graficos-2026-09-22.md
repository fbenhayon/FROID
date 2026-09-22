# A piscada dos gráficos — 22/09/2026

Sintoma relatado: os gráficos aparecem por um segundo e desaparecem. No modo de
atualização de 1 minuto as informações deveriam ficar paradas por esse minuto, e
não ficavam.

## Causa

O motor publica **um tique por segundo** (`froid_stream_loop`, `main.py`) e
declara `apuracao_disponivel: false` em toda janela sem voz vozeada. O próprio
`froid_core.py` descreve essa situação como "metade de qualquer consulta": o
paciente está calado enquanto o profissional fala. Esse payload sai com
`perception_zones: []`, `ipm_score: null` e `coherence_status: "SEM_APURACAO"`.

O painel usava esse instante como porteiro de todos os painéis derivados:

```
semApuracaoAgora = !state.connected || !raw || raw.apuracao_disponivel === false
```

`raw` é o último tique. A cada segundo calado, zonas, IPM, coerência, alertas e
metadados de áudio eram zerados; a primeira sílaba os trazia de volta por um
segundo e o silêncio seguinte os apagava de novo. É a piscada.

No modo de 1 minuto o efeito era pior: o instante derrubava exatamente o
agregado (`clinicalSnapshot`) que a janela clínica existe para segurar parado.
A janela era construída corretamente e nunca chegava à tela inteira.

### Uma causa a montante, no servidor

O laço de tique corre 1x/s; a DSP da janela recebida corre numa thread e nem
sempre termina dentro do mesmo segundo. Entre a chegada do PCM e o fim do
cálculo, `process_tick` declarava ausência — e essa ausência é **falsa**: a
janela chegou e estava sendo medida naquele instante. Publicada, ela chegava ao
painel como um tique sem apuração no meio de tiques medidos.

O motor já separava esse caso: `estado: "analisando"` com
`motivo: "analise_pendente"` é a única combinação que significa "ainda não sei",
em vez de "não houve". Faltava o laço consumir a distinção — o mesmo padrão da
casa, a peça existia e ninguém a lia.

Havia um teste exigindo exatamente isso
(`test_tick_aguarda_dsp_em_andamento_sem_publicar_ausencia_transitoria`), e ele
estava **vermelho**: escrito, sem implementação. A nota de 22/09 registrou "72
testes locais selecionados" passando; esta suíte inteira não tinha sido rodada.

Duas causas secundárias, no mesmo sintoma:

- **Ponto medido sozinho não desenhava nada.** O caminho do `IPMLineChart` só
  liga `L` entre segundos consecutivos — correto, porque ligar por cima de uma
  lacuna inventaria medida. Mas fala em rajadas curtas entre silêncios produz
  pontos isolados, que saem como `M x,y`: `M` apenas move a caneta. O SVG ficava
  em branco com `pts.length > 0`.
- **`SEM_APURACAO` vazando do agregado.** `aggregatePayloads` copia a coerência
  do último payload da janela de 3 s, que pode ser um tique calado. O RiskChart
  lê essa string como ausência e apagava, enquanto as zonas ao lado seguiam na
  tela — painel se contradizendo.

Este é o mesmo defeito que `estado-da-captura.ts` já havia corrigido no alarme,
com o relato idêntico do profissional: "fica entrando e saindo, parece
instável". A regra existia e não valia na apresentação.

## Correção

A regra desta casa já estava escrita em `PATIENT_AUDIO_GRACE_MS`: "o silêncio
clínico é dado, não ausência de sinal". Ela valia só no portão das métricas.
Agora vale também na apresentação.

- O reducer guarda `lastMeasured` — o último tique que mediu e o segundo em que
  mediu. Tique calado não derruba: apenas deixa envelhecer. Socket caído
  (`WS_CLOSE`, `SEM_LEITURA`) limpa, porque não é silêncio do paciente.
- A apresentação confere a idade contra um horizonte. Fora dele, a tela volta a
  declarar ausência — reter além do horizonte seria o defeito oposto.
  - Modo clínico: o horizonte é a janela escolhida (1min → 60 s).
  - Tempo real e gráficos de detalhe: 20 s, o mesmo `PATIENT_AUDIO_GRACE_MS`.
- `current` do `IPMLineChart` continua sendo o **instante**: é ele que acende
  "ao vivo" ou "Sem leitura atual" e imprime o número grande. A série retém o
  que foi medido; o rótulo nunca chama o retido de atual.
- Cada ponto sem vizinho contíguo ganha um disco próprio. Mesma medida, visível.
- `SEM_APURACAO` é recusada como valor de coerência e cai na última medida.
- No servidor, `froid_stream_loop` retém a ausência transitória: só ela, e a
  espera é limitada pelo próprio motor — passados `VALIDADE_VOZ_S` (4 s) o PCM
  vence, o estado deixa de ser `analisando` e o tique seguinte publica a
  ausência de verdade. Folga confortável ante o watchdog de 8 s do painel.
  Silêncio, PCM vencido e ausência de áudio continuam sendo publicados no tique
  em que acontecem.

## Dois testes que estavam errados

- `test_publicacao_acustica.py` afirmava `payload["apuracao_disponivel"]` num
  tique medido. A chave **só existe no payload de ausência**, com valor `False`;
  o payload medido não a carrega — por isso o painel compara com `=== false`. A
  asserção levantava `KeyError` contra um tique perfeitamente medido. Passou a
  ler os marcadores de procedência (`estado_da_captura`, `voice_features_source`).
- `test_aleatoriedade_confinada.py` fixava o **nome** `semApuracaoAgora` por
  busca no fonte. A substância que ele guarda — sem apuração, os gráficos
  derivados recebem vazio — continua valendo e continua testada; mudou o
  critério, de tique para janela. Somaram-se dois casos: o portão é a janela, e
  a retenção **tem** horizonte.

## Verificação

- Painel: 800 testes em 55 arquivos, incluindo 16 novos em
  `retencao-da-apuracao.test.tsx` — retenção no reducer, horizonte por modo,
  socket caído, coerência e pontos isolados.
- Servidor: 1.842 testes e 5.820 subtestes, 79 pulados, nenhuma falha. A suíte
  **inteira** foi executada, não uma seleção.
- TypeScript sem erro e build do Vite concluído.

Os testes novos do painel exercitam as declarações reais de `LiveSession.tsx`
por AST, não uma cópia do comportamento.

## Limite desta nota

Nada aqui foi observado numa chamada real com dois participantes depois da
correção. Os testes e o build não substituem essa verificação: eles mostram que
o portão decide certo, não que o aparelho do incidente voltou a medir. A causa
da ausência de medida investigada em 21/09 é outra questão, e continua aberta —
esta correção trata da apresentação e da publicação, não da captura.

Os dois arquivos de 0 byte no servidor (`Unidades`, `dissonâncias`) e o
`froid-dashboard/STATUS_PARA_AMANHA.md` são anteriores a esta sessão, não são
rastreados pelo git e foram deixados como estavam.
