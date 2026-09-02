// Diagnóstico da chamada, dentro do produto.
//
// Por que existe: em 02/09/2026 uma sessão real não conectou áudio nem vídeo, e
// a investigação passou por sete hipóteses lidas no código-fonte — permissão de
// câmera, modo de sessão, TURN, par antigo na sinalização, renegociação, troca
// de trilhas e o monitor de fluxo. Todas corretas. O que faltava era saber em
// QUE ETAPA a conexão morre, e isso só o navegador do usuário sabe.
//
// A alternativa que tentamos primeiro — colar um trecho no console — falhou
// duas vezes, e não por culpa de quem colou: o envelope só captura conexões
// criadas DEPOIS dele, e quando a tela já está montada não há nenhuma. Pedir a
// um profissional em atendimento que acerte esse tempo é pedir demais.
//
// Aqui a captura nasce com a tela e não depende de ninguém acertar o momento.
// Não muda comportamento nenhum: só observa e guarda em memória.

export type EventoRtc = { hora: string; texto: string };

const LIMITE = 200;

let linhas: EventoRtc[] = [];

function agora(): string {
  return new Date().toTimeString().slice(0, 8);
}

export function registrarRtc(texto: string): void {
  linhas.push({ hora: agora(), texto });
  if (linhas.length > LIMITE) linhas = linhas.slice(-LIMITE);
}

export function limparDiagnosticoRtc(): void {
  linhas = [];
}

export function eventosRtc(): EventoRtc[] {
  return [...linhas];
}

/** Texto pronto para colar num chamado de suporte. */
export function relatorioRtc(): string {
  if (!linhas.length) return "Nenhum evento de chamada registrado.";
  return linhas.map((l) => `${l.hora}  ${l.texto}`).join("\n");
}

/** Liga a observação numa conexão recém-criada.
 *
 *  Só escuta eventos. Nenhum `preventDefault`, nenhuma alteração de estado —
 *  um diagnóstico que altera o que observa não serve para diagnosticar. */
export function observarConexao(peer: RTCPeerConnection, papel: string): RTCPeerConnection {
  registrarRtc(`conexão criada (${papel})`);

  const servidores = (peer.getConfiguration().iceServers || [])
    .flatMap((s) => (Array.isArray(s.urls) ? s.urls : [s.urls]))
    .map((u) => String(u || ""));
  const temTurn = servidores.some((u) => u.toLowerCase().startsWith("turn"));
  registrarRtc(
    `servidores ICE: ${servidores.length} (${temTurn ? "com TURN" : "SEM TURN"})`,
  );

  peer.addEventListener("iceconnectionstatechange", () =>
    registrarRtc(`ICE: ${peer.iceConnectionState}`),
  );
  peer.addEventListener("connectionstatechange", () =>
    registrarRtc(`conexão: ${peer.connectionState}`),
  );
  peer.addEventListener("signalingstatechange", () =>
    registrarRtc(`sinalização: ${peer.signalingState}`),
  );
  peer.addEventListener("icegatheringstatechange", () =>
    registrarRtc(`coleta de candidatos: ${peer.iceGatheringState}`),
  );
  peer.addEventListener("track", (evento) =>
    registrarRtc(`CHEGOU mídia do outro lado: ${evento.track.kind}`),
  );
  peer.addEventListener("icecandidateerror", (evento) => {
    const e = evento as RTCPeerConnectionIceErrorEvent;
    registrarRtc(`erro de candidato ICE ${e.errorCode}: ${e.errorText || ""}`);
  });

  return peer;
}

/** Descreve o que está sendo enviado — a pergunta "eu estou transmitindo?".
 *
 *  Vale registrar porque um dos sintomas possíveis é a conexão subir sem
 *  trilha nenhuma, e de fora isso é indistinguível de falha de rede. */
export function registrarEnvio(peer: RTCPeerConnection): void {
  const enviando = peer
    .getSenders()
    .filter((s) => s.track)
    .map((s) => s.track?.kind)
    .join(", ");
  registrarRtc(enviando ? `enviando: ${enviando}` : "NÃO está enviando trilha alguma");
}
