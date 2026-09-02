# Incidente — vídeo e áudio não conectam entre profissional e paciente

Aberto em 02/09/2026, durante atendimento real. **Não resolvido.**

## O sintoma, com precisão

- Profissional **vê o próprio vídeo**. Paciente **vê o próprio vídeo**.
- A sinalização funciona: o profissional recebe `patient_joined` e a tela mostra
  "O paciente está na sala".
- **Nenhuma mídia atravessa** em nenhuma direção.
- A tela exibe *"Falta ele liberar câmera e microfone no próprio aparelho"* — e isso é
  **diagnóstico errado**, ver a seção de defeitos abaixo.
- O aviso registrou que o paciente **abriu o link 3 vezes**.
- Paciente está em **computador**, não celular.
- Sessão criada no modo **remoto**, confirmado pelo Fábio.
- Dezenas de sessões já funcionaram antes com este mesmo sistema.

## Hipóteses DESCARTADAS — não repetir

| # | Hipótese | Como foi descartada |
|---|---|---|
| 1 | Permissão de câmera negada | Os dois lados têm vídeo local funcionando |
| 2 | Modo de sessão errado (`presential` / `presential_mobile`) | Fábio confirmou: sessão remota |
| 3 | TURN ausente ou inacessível | `/health` responde `turn_configured: true`, `turn_reachable: true`, respondendo em `:3478` |
| 4 | Par antigo travando a sala de sinalização | `RtcSignalManager.connect` fecha o socket antigo (código 4000) e assume o lugar. Correto |
| 5 | Falta de renegociação quando o paciente reentra | Tratado em `LiveSession.tsx`: `peer-joined` chama `makeOffer(true)`, com comentário documentando o impasse de 26/08/2026 |

**Erro meu que vale registrar:** afirmei que "a infraestrutura de TURN nunca foi ligada"
lendo o `.env` **local** e concluindo sobre produção. São arquivos diferentes. O Fábio
corrigiu, e a sonda do `/health` provou que ele estava certo.

## O que falta capturar

Nada disso existe ainda, e sem isso a investigação continua sendo adivinhação:

1. **Console do navegador do profissional** durante a tentativa (F12 → Console).
2. **Console do navegador do paciente**, idem.
3. **Estado ICE dos dois lados.** Em `chrome://webrtc-internals` (Chrome) ou
   `about:webrtc` (Firefox), com a sessão aberta: qual o `iceConnectionState` final, e se
   algum par de candidatos chegou a `succeeded`.
4. **Log do backend** durante a tentativa:
   `docker compose logs --tail=200 froid-backend | grep -i "rtc\|signal\|ws"`

## Por onde começar na próxima sessão

O quadro é estranho e vale nomear: sinalização viva, TURN saudável, renegociação tratada,
e mídia nenhuma. Isso aponta para algo entre a oferta e o fluxo de mídia — candidatos ICE
que não chegam, trilhas que não são adicionadas ao peer, ou a oferta saindo sem `m-lines`.

Sugestões de ponto de entrada, em ordem:

- `froid-dashboard/src/pages/LiveSession.tsx` — `makeOffer`, e o que acontece quando ela é
  forçada com uma oferta pendente.
- `froid-dashboard/src/lib/webrtc.ts` — `activateRtcRelayFallback` só age se houver TURN;
  há TURN, então vale ver se ele chega a ser chamado e o que acontece depois.
- `froid-dashboard/src/pages/PatientSessionPage.tsx` — linha ~352 tem o estado *"A chamada
  conectou sem transmitir câmera e microfone"*. Se esse estado for atingido, ele descreve
  o sintoma quase exatamente.

## Defeito secundário, confirmado e independente da causa

A mensagem *"O paciente está na sala. Falta ele liberar câmera e microfone no próprio
aparelho"* é escrita a partir do último **evento de sessão** (`patient_joined`) somado à
ausência de mídia remota — ela **não olha** o estado real da mídia do paciente.

Quando o paciente já liberou câmera e microfone, a mensagem acusa algo que ele já fez, e o
profissional passa a cobrar do paciente uma ação impossível de repetir. Num atendimento
clínico isso desgasta a relação e desperdiça o tempo da sessão.

`LiveSession.tsx`, por volta da linha 2506.
