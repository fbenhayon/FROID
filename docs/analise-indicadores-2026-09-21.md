# Indicadores sem atualização durante chamada com áudio e vídeo normais

Investigação de 21/09/2026. Inspeção de produção somente para leitura, pelo
convite informado pelo profissional. Nenhum serviço reiniciado e nenhuma
alteração publicada. Não foram acessados o conteúdo da transcrição nem áudio
do paciente. Esta nota não contém nomes, convites ou credenciais.

## Resultado comprovado

O áudio destinado aos indicadores chegou à rota do servidor e o painel
recebeu amostras. Entretanto, quase todas foram registradas **sem voz medida**.
Isso localiza a ausência antes da apresentação dos índices, no caminho entre
a captura acústica independente e a aceitação da janela pelo motor. Ainda não
identifica qual parte desse caminho produziu o problema.

| Evidência da sessão | Resultado |
|---|---|
| Duração registrada | 1.301 segundos |
| Amostras recebidas pelo painel | 1.303 |
| Amostras registradas com voz real medida | 2 |
| Amostras registradas com face real medida | 1.300 |
| Requisições à rota `acoustic-f0` | 880, todas HTTP 200 |
| Período desses envios | 12:13:35 a 12:35:18 UTC |
| Latência medida no servidor para essa rota | Mediana 36,04 ms; percentil 95 de 43,92 ms; máximo 389,8 ms |
| Conexões de análise aceitas no log do período | 1 |
| Recusas de análise ou erros `tick falhou` encontrados | Nenhum |
| Resumos de cortes gravados | 3 |

Essas latências medem o processamento da requisição no servidor, não o tempo
total de rede percebido pelo navegador. Os envios acústicos mantiveram cerca de
40 requisições por minuto na maior parte do atendimento; o motivo dessa cadência
não foi registrado.

A procedência acima foi lida em `procedenciaDosDados` no relatório persistido
da sessão correspondente ao convite, e as requisições foram correlacionadas à
mesma sessão. No segundo e no terceiro cortes, MFCC7, MFCC9, jitter e shimmer
estão nulos. Há F0 registrada nos cortes, mas isso não comprova apuração dos
demais índices: o motor conserva F0 por um caminho separado.

## Por que os textos dos cortes funcionam

- Transcrição e resumo: áudio recebido pela chamada WebRTC → `MediaRecorder`
  no profissional → `/api/transcribe` → texto → `/api/session-summary`.
- Indicadores: outro `getUserMedia` no paciente, com os processamentos de áudio
  desativados → `AudioWorklet` → `/api/froid/{session_id}/acoustic-f0` → extração
  e aceitação pelo motor → `/ws/fusion/{session_id}` → painel.

A segunda captura não fixa o `deviceId` da trilha usada na chamada. Isso permite
fontes diferentes, mas **não foi comprovado que aconteceu nesta sessão**.
O worklet também utiliza somente o primeiro canal da entrada; a quantidade e
o conteúdo dos canais efetivos desta sessão não foram registrados.

## O aviso não comprova sinal fraco

Em `froid_core.py`, o motor exige o espectro de 12 bandas e uma fração mínima
de quadros reconhecidos como vozeados. Essa decisão não utiliza um limiar de
amplitude. A falta de periodicidade suficiente pode produzir
`estado_da_captura="sem_vozeamento"`; isso não identifica, por si só, silêncio,
volume baixo ou a causa de uma fala não reconhecida.

O texto de `AvisoDeApuracao`, em `LiveSession.tsx`, atribui a situação a sinal
fraco sem ter essa evidência. O número 60 mostrado no aviso é o limiar fixo de
contagem de tiques, não a duração efetivamente medida da ausência de voz.

Além disso, HTTP 200 na rota acústica não comprova voz medida: pode representar
ausência de estado de sessão ou extração sem vozeamento suficiente. O cliente
marca o envio como bem-sucedido sem apresentar o resultado dessa extração.

## Verificações de produção

- Backend iniciado em `2026-09-21T00:07:57Z`, com contador de reinícios zero.
- Um processo Uvicorn configurado, evitando divisão desse estado entre workers.
- Código de `froid_core.py`, `froid_voice.py` e `froid_f0.py` no contêiner igual
  ao local ao normalizar finais de linha.
- JavaScript publicado confirma a captura separada, AudioContext solicitado
  a 16 kHz e envio da taxa efetiva do contexto ao servidor.
- O JavaScript publicado já trata recusas do canal de análise. A expiração de
  login do incidente anterior não foi constatada como causa desta sessão.

## O que falta para fechar a causa

Os logs atuais não guardam o dispositivo, número de canais, tamanho/duração
do PCM, RMS nem a razão de vozeamento de cada requisição. O áudio dessa rota
não é persistido para reprocessamento. Portanto, não é possível determinar,
a partir desses registros, se a captura recebeu outra fonte, um sinal sem
periodicidade suficiente ou um sinal que o detector deixou de reconhecer.

O teste necessário é acompanhar uma fala breve, no dispositivo que apresentou
o problema, registrando somente diagnóstico técnico:

1. Se chamada e análise usam o mesmo dispositivo; canais e taxa efetivos.
2. Taxa declarada, quantidade de amostras e RMS do PCM recebido.
3. Razão de vozeamento retornada pelo extrator para essa mesma janela.
4. Estado de captura emitido pelo motor e recebido pelo painel.

Essas observações distinguem problema de entrada, detecção e apresentação sem
guardar a fala. Até obter essa evidência, não alterar limiares científicos nem
apresentar uma correção de dispositivo como causa comprovada deste incidente.


## Revisão após as alterações publicadas pelo proprietário

Às 15h31 de 21/09/2026, o código local e o servidor estavam em `8f095ca4`.
O commit `d49ed6f7` já incorporava a primeira etapa das correções. Os hashes
de `main.py` e `froid_core.py` dentro do contêiner coincidiam com o servidor.
Os contêineres haviam iniciado às 12h39 de Brasília. O JavaScript público
também continha a nova captura e o diagnóstico.

A revisão encontrou duas incompatibilidades não cobertas pelos testes anteriores:

- A rota responde `status="processed"`, mas a captura esperava `"ok"` e emitia
  erro mesmo após processamento. O cliente agora reconhece `processed`;
  `session_inactive`, resposta inválida e `superseded` continuam distintos.
- O cliente envia `captura_cliente`, mas a rota buscava `diagnostico_acustico`
  no pedido. Corrigida a leitura do campo, mantendo a filtragem de atributos.
  Nome e identificador do microfone não são publicados.

Mute e suspensão agora interrompem a sequência mesmo sem janela inteira
pendente; trilha desabilitada informa ausência; navegador sem AudioWorklet
declara falta de suporte. Não houve alteração do YIN ou de critérios científicos.

### Validação desta etapa

- Painel: 757 testes existentes passaram; 18 novos testes de execução da captura
  passaram. Cobrem dispositivo, metadados, resposta, rede, timeout, parada e mute.
- Backend: 24 testes focados passaram localmente e na imagem nova, em contêiner
  descartável sem rede ou volumes de produção. Exercitam a rota real isolada
  por AST, DSP real, diagnóstico até o tick, silêncio, duplicatas, autorização,
  validade e substituição de janelas.
- A suíte geral local executou 1.868 testes e terminou com cinco erros por falta
  de FastAPI/pytest e 75 testes pulados. Não foi inteiramente verde. Os três
  casos de recusa de WebSocket afetados pela falta do FastAPI passaram depois
  na imagem isolada.
- TypeScript e build do painel passaram localmente; ambas as imagens Docker
  foram construídas com sucesso no servidor.
- O ensaio de downmix no Chrome não concluiu: a navegação do teste foi abortada
  antes de executar o código. Os testes confirmam a configuração mono, mas não
  há validação concluída em navegador real nesta etapa.

### Estado da publicação

O proprietário autorizou atualizar o servidor. Quatro arquivos foram enviados
após conferir commit e hashes, preservando as demais alterações:

- `froid-dashboard/src/lib/froid-acoustic.ts`
- `froid-server/main.py`
- `froid-dashboard/src/lib/captura-acustica-runtime.test.ts`
- `froid-server/tests/test_acoustic_transport_contract.py`

Backup dos arquivos e referências das imagens anteriores:
`/root/froid-deploy-backups/acustica-20260921T184246Z`.
As imagens anteriores também receberam tags de retorno.

**Ativação concluída em 21/09/2026 às 15h54 de Brasília.** Após o bloqueio
inicial da revisão automática, o proprietário autorizou explicitamente a
ativação mesmo com interrupção de consultas. Backend e painel foram recriados
com as imagens testadas e ambos atingiram o estado `healthy`.

Verificações após a ativação:

- O hash de `main.py` dentro do backend coincide com a correção enviada.
- A aplicação pública e `/health` responderam HTTP 200.
- O arquivo público `/assets/webrtc-Asqh1NFy.js` é idêntico ao do contêiner e
  contém reconhecimento de `processed`, `captura_cliente` e `capture_sequence`.
  Os assets ficam em `/assets/`, conforme o índice, e não em `/app/assets/`.
- Nenhum traceback nem erro `tick falhou` nos logs entre a ativação e a
  conferência final.

Não houve commit nem push nesta etapa. Confirmar o funcionamento no dispositivo
do incidente ainda exige uma nova fala capturada nesse dispositivo.
