# Incidente — vídeo e áudio não conectam entre profissional e paciente

Aberto em 02/09/2026, durante atendimento real. **Causa encontrada e corrigida no
mesmo dia** — com uma ressalva importante na última seção.

## O sintoma, com precisão

- Profissional **vê o próprio vídeo**. Paciente **vê o próprio vídeo**.
- A sinalização funciona: o profissional recebe `patient_joined` e a tela mostra
  "O paciente está na sala".
- **Nenhuma mídia atravessa** em nenhuma direção.
- Paciente em **computador**, uma aba só. Sessão criada no modo **remoto**.
- Dezenas de sessões já haviam funcionado com este mesmo sistema.

## A causa: a recuperação de erro virou o erro

O diagnóstico embutido no produto (`lib/diagnostico-rtc.ts`) produziu, do lado do
profissional, este par repetindo cerca de duas vezes por segundo durante vinte
segundos:

```
sinalização: stable
coleta de candidatos: new
sinalização: have-local-offer
coleta de candidatos: gathering
```

O que **não** aparece no log é o que resolveu o caso: nenhum `ICE: checking`,
nenhum `conexão: connecting`, nenhum `CHEGOU mídia`. A conexão nunca chegava a
*tentar* conectar. Era reiniciada antes.

O mecanismo, fechado nos dois sentidos:

1. Uma oferta falha ao ser aplicada no paciente.
2. O `catch` do paciente pede `renegotiate-request` — **na hora, sem limite**.
3. O profissional responde com `restartIce()` + `makeOffer(true)`, que faz
   *rollback* (`→ stable`) e cria oferta nova (`→ have-local-offer`) — o par
   exato que o log repete.
4. A oferta nova falha pelo mesmo motivo da primeira. Volta ao passo 2.

Negociar uma conexão leva **segundos**. O laço não dava **milissegundos**. Nem
uma vez o ICE teve tempo de tentar.

## Por que oito hipóteses passaram sem achar

Os dois lados escreviam a mesma linha:

```js
.catch(() => {                                  // o erro é DESCARTADO
  sendSignal({ type: "renegotiate-request" });  // e a operação se repete
});
```

O objeto de erro nunca era lido. A frase do navegador que dizia *por que* a
oferta não pôde ser aplicada foi destruída a cada volta do laço — milhares de
vezes ao longo da investigação. Sem ela, sobrou adivinhar, e adivinhamos oito
vezes.

**Erro meu que vale registrar:** afirmei que "a infraestrutura de TURN nunca foi
ligada" lendo o `.env` **local** e concluindo sobre produção. São arquivos
diferentes. O Fábio corrigiu, e a sonda do `/health` provou que ele estava certo.

## Hipóteses descartadas — não repetir

| # | Hipótese | Como foi descartada |
|---|---|---|
| 1 | Permissão de câmera negada | Os dois lados têm vídeo local funcionando |
| 2 | Modo de sessão errado (`presential`) | Sessão remota, confirmado |
| 3 | TURN ausente ou inacessível | `/health`: `turn_configured` e `turn_reachable` verdadeiros |
| 4 | Par antigo travando a sala | `RtcSignalManager.connect` fecha o antigo com 4000, que é código **terminal** — o expulso não volta, então não há ping-pong |
| 5 | Falta de renegociação ao reentrar | Tratado: `peer-joined` chama `makeOffer(true)` |
| 6 | Laço de `onnegotiationneeded` | Não existe handler desse evento em nenhum dos dois lados |
| 7 | Cão de guarda da oferta reofertando | Ele é de 8 segundos; o laço era de 500 ms |
| 8 | Duas abas do paciente | Uma só, confirmado — e o item 4 mostra que nem duas explicariam |

## O que mudou

| Onde | Mudança |
|---|---|
| `lib/webrtc.ts` | `criarFreioDeRenegociacao` — espaçamento mínimo de 2 s, 4 tentativas, cota devolvida quando a conexão sobe ou após 30 s quietos |
| `lib/diagnostico-rtc.ts` | `registrarFalha` grava a mensagem real do navegador; `incorporarRelatorioRemoto` junta os dois lados num relatório só |
| `pages/PatientSessionPage.tsx` | Ganhou o diagnóstico que só o profissional tinha; renegociação passa pelo freio; o relatório dele viaja pela sinalização até o painel |
| `pages/LiveSession.tsx` | `renegotiate-request` passa pelo freio; pede o relatório do paciente quando a cota acaba |
| `pages/PatientSessionPage.tsx` | `reconnectAttempt = 0` saiu do `onopen`: um socket que abria e fechava reabria para sempre, porque cada abertura apagava o histórico de fracasso. Agora só conta o socket que se sustenta 5 s |

Nada disso exige o backend: `RtcSignalManager.relay` já repassa qualquer
dicionário, sem lista de tipos permitidos. **Só o frontend precisa de rebuild.**

Testes: `lib/freio-renegociacao.test.ts` (13), incluindo a regressão direta —
cem falhas em um segundo produzem **uma** renegociação, não cem.

## A causa de origem: o rollback

O diagnóstico da segunda tentativa trouxe a frase que faltava, dos dois lados:

```
seu lado      The order of m-lines in answer doesn't match order in offer
lado paciente The order of m-lines in subsequent offer doesn't match order
              from previous offer/answer
```

E o log flagrou o instante, às 11:54:54, tudo dentro do mesmo segundo:

```
have-local-offer     ← oferta A
stable               ← ROLLBACK
have-local-offer     ← oferta B
FALHOU ... the order of m-lines in answer doesn't match order in offer
```

`makeOffer(true)` desfazia a oferta pendente com `setLocalDescription({type:
"rollback"})` antes de criar outra. A resposta do paciente era da oferta A e
chegou quando o local já era a oferta B. O navegador recusou.

O estrago não parou aí. O peer do paciente **já havia negociado** com a ordem
antiga — o log dele mostra `CHEGOU mídia: audio`, `CHEGOU mídia: video`,
`ICE: checking`, `conexão: connecting`. A chamada estava subindo. A partir do
desalinhamento, ele passou a recusar **toda** oferta seguinte: seis recusas
idênticas até `failed`. A ordem das m-lines de um peer negociado não muda mais,
e nenhuma renegociação conserta isso.

Duas camadas, então:

- **origem** — o rollback, que embaralhava a ordem entre uma oferta e a seguinte;
- **amplificador** — o laço de renegociação, que respondia a um erro
  irrecuperável repetindo a operação que acabara de falhar.

## O que mudou na segunda rodada

| Onde | Mudança |
|---|---|
| `LiveSession.tsx` | **O rollback saiu do código.** Forçar uma oferta agora *reenvia a pendente*: ela continua válida, e reenviar não reordena nada. O cão de guarda de 8 s também reenvia |
| `LiveSession.tsx` / `PatientSessionPage.tsx` | Cada oferta leva `seq`; a resposta devolve o número; resposta de oferta superada é **descartada**, não aplicada |
| `lib/webrtc.ts` | `eDesalinhamentoDeMlines` reconhece o erro pelo nome |
| ambos | Ao detectá-lo, o peer é **reconstruído do zero** — com teto de 2, para a recuperação não virar o laço que veio resolver |

O impasse que o rollback resolvia (uma oferta entregue à sala vazia) continua
resolvido: a sala agora tem alguém, então a mesma oferta serve.

## O que este incidente ensinou sobre os testes

`sinalizacao-par-ausente.test.ts` **exigia** o rollback — a linha
`expect(trecho).toContain('setLocalDescription({ type: "rollback" })')`. O teste
tinha congelado o mecanismo em vez da garantia, e por isso protegia o defeito.

Foi reescrito para exigir o que de fato importa: quem acaba de entrar não pode
ficar travado por uma oferta entregue à sala vazia. O meio ficou livre.

## Se acontecer de novo

Abra o diagnóstico da chamada. Ele traz os dois lados, separados por
`--- daqui para baixo, o relatorio do PACIENTE ---`. As três linhas que decidem:

- `NEGOCIADO:` — se disser `NAO envia`, `recvonly` ou `nenhum transceptor`, o
  problema é configuração de trilha, não rede;
- `FALHOU em` — a mensagem literal do navegador;
- `ICE:` — se nunca chegar a `checking`, a conexão está sendo reiniciada antes
  de tentar.
