import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { apiUrl, wsUrl } from "../lib/api";
import {
  observarConexao,
  registrarEnvio,
  registrarFalha,
  registrarNegociacao,
  registrarRtc,
  relatorioRtc,
} from "../lib/diagnostico-rtc";
import {
  activateRtcRelayFallback,
  criarFreioDeRenegociacao,
  eDesalinhamentoDeMlines,
  motivoDaRecusaDeSinalizacao,
  adoptRemoteTrack,
  attachRemoteMedia,
  configureConferenceSender,
  createConferenceStream,
  evaluateInboundFlow,
  evaluateOutboundFlow,
  loadRtcConfiguration,
  readRtcMediaFlowStats,
  requestScreenWakeLock,
  shouldReconnectRtcSignaling,
  type RtcMediaFlowStats,
  type ScreenWakeLock,
} from "../lib/webrtc";
import { normalizeSessionLocale, patientCopy, type SessionLocale } from "../lib/localization";
import { STATUS_CAPTURA_TEXTO, startF0Capture } from "../lib/froid-acoustic";
import { startFaceCapture } from "../lib/froid-face";

type JoinState = "checking" | "joined" | "blocked";
type MediaState = "idle" | "requesting" | "active" | "failed";

export const PatientSessionPage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionId = "" } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite") || "";
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // Bloqueio automático de tela pausa a captura de câmera/microfone do
  // celular sem aviso na interface; mantemos a tela acordada com a mídia ativa.
  const wakeLockRef = useRef<ScreenWakeLock | null>(null);
  // Para a captura de PCM do microfone (análise de F0 real).
  const f0StopRef = useRef<null | (() => void)>(null);
  // Para a captura facial (blendshapes -> AUs FACS reais).
  const faceStopRef = useRef<null | (() => void)>(null);
  const rtcSignalRef = useRef<WebSocket | null>(null);
  const rtcPeerRef = useRef<RTCPeerConnection | null>(null);
  const rtcRemoteStreamRef = useRef<MediaStream | null>(null);
  const rtcIceQueueRef = useRef<RTCIceCandidateInit[]>([]);
  // Sobrevive a reconstrucao do peer, porque e ela que este numero conta.
  const reconstrucoesRtcRef = useRef(0);
  const rtcReconnectTimerRef = useRef<number | null>(null);
  const rtcDisconnectTimerRef = useRef<number | null>(null);
  const rtcMediaHealthTimerRef = useRef<number | null>(null);
  const rtcClosingRef = useRef(false);
  const [joinState, setJoinState] = useState<JoinState>("checking");
  const [mediaState, setMediaState] = useState<MediaState>("idle");
  const [callStatus, setCallStatus] = useState("Aguardando profissional");
  const [remoteProfessionalOn, setRemoteProfessionalOn] = useState(false);
  const [remoteProfessionalVideoOn, setRemoteProfessionalVideoOn] = useState(false);
  const [patientName, setPatientName] = useState("");
  // Quantas vezes ESTE convite ja foi aberto. O servidor sempre devolveu
  // `join_count` e ninguem lia. Quando e maior que um, quase sempre significa
  // que a sessao esta aberta em outro aparelho ou em outra aba — e o servidor
  // guarda um socket por papel, entao o aparelho que entrar por ultimo
  // desconecta o anterior. Dizer isso ANTES vale mais do que explicar depois.
  const [aberturasAnteriores, setAberturasAnteriores] = useState(0);
  const [error, setError] = useState("");
  // Fim deliberado da consulta (sinal explícito do profissional, distinto de
  // uma queda de rede transitória) — habilita o encaminhamento do paciente à
  // área restrita dele.
  const [sessionEnded, setSessionEnded] = useState(false);
  // Presencial com celular: o dispositivo do paciente é a captura dedicada
  // (câmera/microfone voltados a ele); o profissional deliberadamente não
  // envia mídia de volta (transceptores recvonly no lado dele). Sem essa
  // distinção, o monitor de fluxo de entrada trata a ausência perpétua de
  // mídia do profissional como falha e força relay TURN + restartIce em
  // loop — dando a impressão de trilhas de áudio/vídeo embaralhadas.
  const [sessionMode, setSessionMode] = useState<"remote" | "presential_mobile">("remote");
  const [uiLocale, setUiLocale] = useState<SessionLocale>(() =>
    normalizeSessionLocale(typeof navigator === "undefined" ? "" : navigator.language),
  );
  const copy = patientCopy(uiLocale);

  const cleanupRtc = () => {
    rtcClosingRef.current = true;
    if (rtcReconnectTimerRef.current) {
      window.clearTimeout(rtcReconnectTimerRef.current);
      rtcReconnectTimerRef.current = null;
    }
    if (rtcDisconnectTimerRef.current) {
      window.clearTimeout(rtcDisconnectTimerRef.current);
      rtcDisconnectTimerRef.current = null;
    }
    if (rtcMediaHealthTimerRef.current) {
      window.clearInterval(rtcMediaHealthTimerRef.current);
      rtcMediaHealthTimerRef.current = null;
    }
    rtcSignalRef.current?.close();
    rtcSignalRef.current = null;
    rtcPeerRef.current?.close();
    rtcPeerRef.current = null;
    rtcRemoteStreamRef.current = null;
    rtcIceQueueRef.current = [];
    setRemoteProfessionalOn(false);
    setRemoteProfessionalVideoOn(false);
    setCallStatus("Aguardando profissional");
    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = null;
    }
    if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
  };

  useEffect(() => {
    let active = true;
    if (!sessionId || !inviteToken) {
      setJoinState("blocked");
      setError("Link de sessão incompleto.");
      return;
    }

    fetch(apiUrl(`/api/patient-sessions/${sessionId}/join`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invite_token: inviteToken }),
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Sessão indisponível.");
        return data;
      })
      .then((data) => {
        if (!active) return;
        setPatientName(String(data?.patient_name || ""));
        setAberturasAnteriores(Math.max(0, Number(data?.join_count || 1) - 1));
        setSessionMode(data?.session_mode === "presential_mobile" ? "presential_mobile" : "remote");
        const nextLocale = normalizeSessionLocale(data?.patient_ui_locale, uiLocale);
        setUiLocale(nextLocale);
        document.documentElement.lang = nextLocale;
        setJoinState("joined");
      })
      .catch((err) => {
        if (!active) return;
        setJoinState("blocked");
        setError(err instanceof Error ? err.message : "Não foi possível entrar.");
      });

    return () => {
      active = false;
      cleanupRtc();
      try {
        f0StopRef.current?.();
      } catch {
        /* noop */
      }
      f0StopRef.current = null;
      try {
        faceStopRef.current?.();
      } catch {
        /* noop */
      }
      faceStopRef.current = null;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      void wakeLockRef.current?.release().catch(() => undefined);
      wakeLockRef.current = null;
    };
  }, [inviteToken, sessionId]);

  // Credencial de TURN buscada assim que a pagina entra na sessao, e nao no
  // toque do botao.
  //
  // `activateMedia` ja disparava isto, mas so quando a pessoa toca "Ativar
  // camera e microfone" — e a partir dali corre em paralelo com o pedido de
  // permissao, que e o trecho lento. Buscar na montagem tira a requisicao do
  // caminho critico por inteiro: quando a permissao e concedida, a
  // configuracao ja esta em cache (`loadRtcConfiguration` memoriza por sessao
  // ate a credencial expirar) e o RTCPeerConnection nasce na hora.
  //
  // Custo de errar: uma requisicao a mais para quem abre o link e desiste.
  // Custo de nao fazer: uma ida ao servidor no exato momento em que o
  // profissional esta olhando para "Aguardando paciente...".
  useEffect(() => {
    if (joinState !== "joined" || !sessionId || !inviteToken) return;
    void loadRtcConfiguration({ sessionId, inviteToken });
  }, [joinState, sessionId, inviteToken]);

  useEffect(() => {
    // O wake lock é liberado automaticamente pelo navegador quando a aba
    // perde visibilidade; ao voltar, se a mídia ainda estiver ativa,
    // pedimos de volta para o celular não travar a captura no meio da sessão.
    const reacquireWakeLock = () => {
      if (document.visibilityState !== "visible") return;
      if (mediaState !== "active") return;
      if (wakeLockRef.current) return;
      requestScreenWakeLock().then((lock) => {
        wakeLockRef.current = lock;
      });
    };
    document.addEventListener("visibilitychange", reacquireWakeLock);
    return () => document.removeEventListener("visibilitychange", reacquireWakeLock);
  }, [mediaState]);

  const replaceOutgoingTracks = async (localConferenceStream: MediaStream) => {
    const peer = rtcPeerRef.current;
    const signal = rtcSignalRef.current;
    const peerAlive = peer
      && peer.connectionState !== "closed"
      && peer.connectionState !== "failed"
      && peer.signalingState !== "closed";
    if (!peerAlive || signal?.readyState !== WebSocket.OPEN) return false;
    const senders = peer.getSenders();
    for (const track of localConferenceStream.getTracks()) {
      const sender = senders.find((item) => item.track?.kind === track.kind);
      if (!sender) return false;
      try {
        await sender.replaceTrack(track);
        await configureConferenceSender(sender);
      } catch {
        return false;
      }
    }
    return true;
  };

  const startPatientRtc = async (localSource: MediaStream) => {
    if (!sessionId || typeof RTCPeerConnection === "undefined") {
      setCallStatus("WebRTC indisponível neste navegador.");
      return;
    }
    // Presencial com celular: o profissional nunca envia áudio/vídeo de
    // volta (recvonly do lado dele) — a ausência de mídia de entrada aqui é
    // o comportamento esperado e permanente, não uma falha a corrigir.
    const isPresentialMobile = sessionMode === "presential_mobile";

    const localConferenceStream = createConferenceStream(localSource);
    if (!localConferenceStream.getTracks().length) {
      setCallStatus("Áudio e vídeo locais indisponiveis para chamada.");
      return;
    }

    // Reaproveita a conexão viva trocando apenas as trilhas nos senders:
    // sem novo ICE nem oferta, e o profissional mantém os mesmos objetos de
    // trilha remota — impossível acumular trilha antiga com nova.
    if (await replaceOutgoingTracks(localConferenceStream)) {
      setCallStatus("Câmera e microfone atualizados na chamada atual.");
      return;
    }

    cleanupRtc();
    rtcClosingRef.current = false;

    const peer = observarConexao(
      new RTCPeerConnection(await loadRtcConfiguration({ sessionId, inviteToken })),
      "paciente",
    );
    // Sem freio, a recuperacao de erro vira o proprio erro: ver
    // `criarFreioDeRenegociacao` em lib/webrtc.ts.
    const freioRenegociacao = criarFreioDeRenegociacao();
    const remoteStream = new MediaStream();
    rtcPeerRef.current = peer;
    rtcRemoteStreamRef.current = remoteStream;

    localConferenceStream.getTracks().forEach((track) => {
      const sender = peer.addTrack(track, localConferenceStream);
      void configureConferenceSender(sender);
    });
    // O que o paciente envia nunca era registrado: no relatorio, o lado
    // dele aparecia sem trilha alguma, e isso e indistinguivel de falha.
    registrarEnvio(peer);

    const sendSignal = (payload: Record<string, unknown>) => {
      const socket = rtcSignalRef.current;
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(payload));
      }
    };

    // O que o paciente sabe, so ele sabe — e ele nao tem console, nao tem
    // painel e nao tem suporte. O relatorio viaja pela propria sinalizacao ate
    // o profissional, que tem onde ler. Uma vez por conta propria; sempre que
    // o profissional pedir.
    let diagnosticoEnviado = false;
    const enviarDiagnostico = (pedidoPeloProfissional = false) => {
      if (diagnosticoEnviado && !pedidoPeloProfissional) return;
      diagnosticoEnviado = true;
      sendSignal({ type: "diagnostico", texto: relatorioRtc() });
    };

    const flushIceQueue = async () => {
      const queued = [...rtcIceQueueRef.current];
      rtcIceQueueRef.current = [];
      for (const candidate of queued) {
        await peer.addIceCandidate(candidate).catch(() => undefined);
      }
    };

    const refreshRemoteTracks = () => {
      const media = attachRemoteMedia(
        remoteStream,
        remoteVideoRef.current,
        remoteAudioRef.current,
      );
      // A existência de trilha só pode rebaixar o status; quem promove para
      // "ativo" é o monitor de fluxo real (getStats), nunca a negociação.
      if (!media.audio) setRemoteProfessionalOn(false);
      if (!media.video) setRemoteProfessionalVideoOn(false);
      setCallStatus(
        media.audio || media.video
          ? "Trilhas do profissional negociadas; validando fluxo real..."
          : isPresentialMobile
            ? "Conectado. Este celular está transmitindo para o profissional."
            : "Conectado, aguardando mídia do profissional.",
      );
    };

    peer.ontrack = (event) => {
      const incomingTracks = event.streams[0]?.getTracks() || [event.track];
      incomingTracks.forEach((track) => {
        adoptRemoteTrack(remoteStream, track);
        track.onended = () => {
          remoteStream.removeTrack(track);
          refreshRemoteTracks();
        };
        track.onmute = refreshRemoteTracks;
        track.onunmute = refreshRemoteTracks;
      });
      refreshRemoteTracks();
    };

    let previousFlowStats: RtcMediaFlowStats | null = null;
    let stalledOutboundChecks = 0;
    // Contador SEPARADO para a mídia de ENTRADA (do profissional). Antes só a
    // saída do paciente escalava para o relay TURN — se a saída funcionasse
    // (rota srflx/srflx direta, comum em NAT de operadora móvel) mas a
    // entrada nunca chegasse (NAT simétrico costuma ser assimétrico entre os
    // dois sentidos), a sessão ficava para sempre em "aguardando a mídia
    // dele", sem nenhum caminho de recuperação.
    let stalledInboundChecks = 0;
    const monitorPatientOutboundMedia = async () => {
      if (peer.connectionState === "closed") return;
      const current = await readRtcMediaFlowStats(peer).catch(() => null);
      if (!current) return;
      const inbound = evaluateInboundFlow(previousFlowStats, current);
      const outbound = evaluateOutboundFlow(previousFlowStats, current);
      previousFlowStats = current;
      if (!inbound || !outbound) return;
      // O que o paciente vê do profissional só fica "ativo" com fluxo real.
      setRemoteProfessionalOn(inbound.audioFlowing);
      setRemoteProfessionalVideoOn(inbound.videoFlowing);
      const route = current.candidateType
        ? ` · rota ${current.candidateType}`
        : "";
      const inboundStalled = !isPresentialMobile
        && !inbound.audioFlowing
        && !inbound.videoFlowing;
      if (peer.connectionState === "connected") {
        if (inboundStalled) {
          stalledInboundChecks += 1;
        } else {
          stalledInboundChecks = 0;
        }
      }
      const escalateToRelay = (reason: string) => {
        stalledOutboundChecks = 0;
        stalledInboundChecks = 0;
        const relayActivated = activateRtcRelayFallback(peer);
        if (relayActivated) {
          peer.restartIce();
          setCallStatus(`${reason} Ativando o relay TURN protegido...`);
          sendSignal({ type: "renegotiate-request" });
          return;
        }
        setMediaState("failed");
        setError(
          "A chamada conectou sem transmitir câmera e microfone. Toque em Ativar câmera e microfone para reconstruir a conexão.",
        );
        sendSignal({ type: "renegotiate-request" });
      };
      if (outbound.audioFlowing && outbound.videoFlowing) {
        stalledOutboundChecks = 0;
        if (inboundStalled && stalledInboundChecks >= 3) {
          escalateToRelay("Enviando normalmente, mas a mídia do profissional nunca chegou;");
          return;
        }
        setCallStatus(
          isPresentialMobile
            ? `Transmitindo áudio e vídeo para o profissional${route}.`
            : inbound.audioFlowing && inbound.videoFlowing
              ? `Áudio e vídeo fluindo nos dois sentidos${route}.`
              : `Transmitindo ao profissional; aguardando a mídia dele (${stalledInboundChecks}/3)${route}.`,
        );
        return;
      }
      if (outbound.audioFlowing || outbound.videoFlowing) {
        // Falha parcial não escala para renegociação: derrubar a trilha que
        // funciona para recuperar a outra é o que gerava a instabilidade.
        stalledOutboundChecks = 0;
        setCallStatus(
          outbound.audioFlowing
            ? `Enviando áudio; vídeo sem saída${route}.`
            : `Enviando vídeo; áudio sem saída${route}.`,
        );
        return;
      }
      if (peer.connectionState !== "connected") return;
      stalledOutboundChecks += 1;
      // Registra os contadores RTP reais para diferenciar "sem saída" de
      // uma janela de leitura sem delta (câmera/microfone realmente parados).
      console.debug(
        `FROID mídia sem saída: audioBytesSent=${current.audioBytesSent} videoFramesEncoded=${current.videoFramesEncoded}`,
      );
      setCallStatus(
        `Conexão ativa, mas mídia sem saída (${stalledOutboundChecks}/3)${route}.`,
      );
      if (stalledOutboundChecks < 3) return;
      escalateToRelay("Rota direta sem mídia;");
    };
    if (rtcMediaHealthTimerRef.current) {
      window.clearInterval(rtcMediaHealthTimerRef.current);
    }
    rtcMediaHealthTimerRef.current = window.setInterval(
      () => void monitorPatientOutboundMedia(),
      2_000,
    );

    peer.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal({ type: "ice", candidate: event.candidate.toJSON() });
      }
    };

    peer.onconnectionstatechange = () => {
      if (peer.connectionState === "connected") {
        freioRenegociacao.liberar();
        reconstrucoesRtcRef.current = 0;
        registrarNegociacao(peer);
        if (rtcDisconnectTimerRef.current) {
          window.clearTimeout(rtcDisconnectTimerRef.current);
          rtcDisconnectTimerRef.current = null;
        }
        refreshRemoteTracks();
      } else if (peer.connectionState === "failed") {
        peer.restartIce();
        sendSignal({ type: "renegotiate-request" });
        setRemoteProfessionalOn(false);
        setRemoteProfessionalVideoOn(false);
        setCallStatus("Reconectando áudio e vídeo do profissional...");
      } else if (peer.connectionState === "disconnected") {
        setCallStatus("Mídia instável; tentando reconectar...");
        if (!rtcDisconnectTimerRef.current) {
          rtcDisconnectTimerRef.current = window.setTimeout(() => {
            rtcDisconnectTimerRef.current = null;
            if (peer.connectionState === "disconnected") {
              peer.restartIce();
              sendSignal({ type: "renegotiate-request" });
            }
          }, 3_000);
        }
      } else if (peer.connectionState === "connecting") {
        setCallStatus("Conectando áudio e vídeo do profissional...");
      }
    };

    let reconnectAttempt = 0;
    const handleSignal = async (event: MessageEvent) => {
      const data = JSON.parse(String(event.data || "{}"));
      // O paciente era inteiramente PASSIVO: tratava `offer`, `ice`,
      // `peer-left` e `session-ended`, e mais nada. Nao tratava `signal-ready`
      // nem `peer-joined` — as duas mensagens que dizem "o profissional esta
      // ai". Ele abria o socket, escrevia "Aguardando chamada do
      // profissional..." e esperava, sem nunca poder pedir a chamada.
      //
      // Isso importa porque o profissional pode estar com uma oferta pendente
      // que foi para a sala vazia enquanto o paciente estava fora. Quem sabe
      // que acabou de entrar e o paciente; pedir a renegociacao daqui e o que
      // tira os dois do impasse quando o `peer-joined` do outro lado se perde.
      if (data.type === "error") {
        setError(
          `A sala recusou a conexão: ${String(data.detail || "motivo não informado")}.`,
        );
        return;
      }
      if (data.type === "pedir-diagnostico") {
        enviarDiagnostico(true);
        return;
      }
      if (data.type === "signal-ready" || data.type === "peer-joined") {
        const profissionalPresente =
          data.type === "peer-joined" || Boolean(data.peer_connected);
        if (profissionalPresente) {
          if (freioRenegociacao.permite()) {
            sendSignal({ type: "renegotiate-request" });
            setCallStatus("Conectando com o profissional...");
          }
        } else {
          setCallStatus("Aguardando chamada do profissional...");
        }
        return;
      }
      if (data.type === "offer" && data.offer) {
        if (peer.signalingState !== "stable") return;
        await peer.setRemoteDescription(data.offer);
        await flushIceQueue();
        const answer = await peer.createAnswer();
        await peer.setLocalDescription(answer);
        // Devolve o numero da oferta: e assim que o profissional distingue
        // esta resposta de uma resposta atrasada, que ele agora descarta em
        // vez de aplicar contra a oferta seguinte.
        sendSignal({ type: "answer", answer: peer.localDescription, seq: data.seq });
        setCallStatus("Respondendo ao profissional...");
      } else if (data.type === "ice" && data.candidate) {
        if (peer.remoteDescription) {
          await peer.addIceCandidate(data.candidate).catch(() => undefined);
        } else {
          rtcIceQueueRef.current.push(data.candidate);
        }
      } else if (data.type === "peer-waiting") {
        // Mesma mensagem, outro lado: o profissional ainda nao entrou na sala.
        // Dizer isso evita a espera silenciosa que fazia o paciente desistir
        // achando que o link estava quebrado.
        setCallStatus(
          "O profissional ainda não entrou na sala. Deixe esta página aberta: a chamada começa sozinha assim que ele entrar.",
        );
      } else if (data.type === "peer-left") {
        remoteStream.getTracks().forEach((track) => {
          track.stop();
          remoteStream.removeTrack(track);
        });
        setRemoteProfessionalOn(false);
        setRemoteProfessionalVideoOn(false);
        setCallStatus("Profissional saiu da chamada.");
        if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
        if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
      } else if (data.type === "session-ended") {
        // Encerramento deliberado pelo profissional: libera câmera/microfone e
        // as capturas de análise, e habilita o encaminhamento à área do paciente.
        try {
          f0StopRef.current?.();
        } catch {}
        f0StopRef.current = null;
        try {
          faceStopRef.current?.();
        } catch {}
        faceStopRef.current = null;
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        void wakeLockRef.current?.release().catch(() => undefined);
        wakeLockRef.current = null;
        if (videoRef.current) videoRef.current.srcObject = null;
        if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
        if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
        setRemoteProfessionalOn(false);
        setRemoteProfessionalVideoOn(false);
        setCallStatus("Sessão encerrada pelo profissional.");
        setSessionEnded(true);
      }
    };

    let signalQueue: Promise<void> = Promise.resolve();
    let aberturaEstavel: number | null = null;
    const connectSignaling = () => {
      if (rtcClosingRef.current || peer.connectionState === "closed") return;
      const socket = new WebSocket(
        wsUrl(
          `/ws/rtc/${sessionId}/patient?invite=${encodeURIComponent(inviteToken)}`,
        ),
      );
      rtcSignalRef.current = socket;
      socket.onopen = () => {
        // Zerar o contador aqui na hora anulava o limite de tentativas: um
        // socket que abre e fecha em seguida reabre PARA SEMPRE, de meio em
        // meio segundo, porque cada abertura apagava o historico de fracasso.
        // So conta como sucesso o socket que se sustenta.
        aberturaEstavel = window.setTimeout(() => {
          aberturaEstavel = null;
          reconnectAttempt = 0;
        }, 5_000);
        setCallStatus("Aguardando chamada do profissional...");
      };
      socket.onmessage = (event) => {
        signalQueue = signalQueue
          .then(() => handleSignal(event))
          .catch((erro) => {
            // O erro era descartado aqui, e com ele a unica informacao que
            // dizia por que a chamada nao subia.
            registrarFalha("tratar sinal recebido", erro);
            if (eDesalinhamentoDeMlines(erro)) {
              // Seis vezes seguidas, em 02/09/2026, este erro foi respondido
              // com um pedido de renegociacao — que so podia falhar igual,
              // porque a ordem das m-lines de um peer negociado nao muda mais.
              if (reconstrucoesRtcRef.current >= 2) {
                registrarRtc("desalinhamento persistente — parei de reconstruir");
                setCallStatus(
                  "Não foi possível estabelecer a chamada. Recarregue a página.",
                );
                enviarDiagnostico();
                return;
              }
              reconstrucoesRtcRef.current += 1;
              registrarRtc("reconstruindo a conexao do zero");
              setCallStatus("Refazendo a conexão da chamada...");
              void startPatientRtc(localSource);
              return;
            }
            if (freioRenegociacao.permite()) {
              setCallStatus("Sincronizando novamente a chamada...");
              sendSignal({ type: "renegotiate-request" });
              return;
            }
            if (freioRenegociacao.esgotado()) {
              setCallStatus(
                "Nao foi possivel estabelecer audio e video. O profissional ja "
                + "recebeu os detalhes tecnicos desta tentativa.",
              );
              registrarNegociacao(peer);
              enviarDiagnostico();
            }
          });
      };
      socket.onerror = () => socket.close();
      socket.onclose = (event) => {
        if (aberturaEstavel) window.clearTimeout(aberturaEstavel);
        aberturaEstavel = null;
        if (rtcClosingRef.current || peer.connectionState === "closed") return;
        if (!shouldReconnectRtcSignaling(event.code, reconnectAttempt, peer.connectionState)) {
          // O paciente e quem tem menos como descobrir sozinho o que houve:
          // nao tem painel, nao tem suporte, e frequentemente esta no celular.
          // A frase precisa dizer o que ELE pode fazer.
          setCallStatus(motivoDaRecusaDeSinalizacao(event.code));
          setError(motivoDaRecusaDeSinalizacao(event.code));
          return;
        }
        const delay = Math.min(4_000, 500 * 2 ** reconnectAttempt);
        reconnectAttempt += 1;
        setCallStatus("Reconectando sinalização da chamada...");
        rtcReconnectTimerRef.current = window.setTimeout(connectSignaling, delay);
      };
    };
    connectSignaling();
  };

  const activateMedia = async () => {
    if (mediaState === "active" || mediaState === "requesting") return;
    setMediaState("requesting");
    setError("");
    try {
      void loadRtcConfiguration({ sessionId, inviteToken });
      streamRef.current?.getTracks().forEach((track) => track.stop());
      const video = {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 24, max: 30 },
        facingMode: "user",
      } satisfies MediaTrackConstraints;
      const audio = {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      } satisfies MediaTrackConstraints;
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video, audio });
      } catch {
        const tracks: MediaStreamTrack[] = [];
        try {
          const audioCapture = await navigator.mediaDevices.getUserMedia({
            audio,
            video: false,
          });
          tracks.push(...audioCapture.getAudioTracks());
        } catch {
          // Continue para permitir diagnóstico e nova tentativa da câmera.
        }
        try {
          const videoCapture = await navigator.mediaDevices.getUserMedia({
            video,
            audio: false,
          });
          tracks.push(...videoCapture.getVideoTracks());
        } catch {
          // A interface informa exatamente qual trilha não foi liberada.
        }
        if (!tracks.length) throw new Error("camera-and-microphone-unavailable");
        stream = new MediaStream(tracks);
      }
      streamRef.current = stream;
      stream.getTracks().forEach((track) => {
        let muteTimer: number | null = null;
        const markCaptureUnavailable = () => {
          if (track.readyState !== "live" || track.muted) {
            setMediaState("failed");
            setError(
              track.kind === "video"
                ? "A câmera parou de transmitir. Toque em Ativar câmera e microfone para reconectar."
                : "O microfone parou de transmitir. Toque em Ativar câmera e microfone para reconectar.",
            );
          }
        };
        track.onended = markCaptureUnavailable;
        track.onmute = () => {
          if (muteTimer) window.clearTimeout(muteTimer);
          muteTimer = window.setTimeout(markCaptureUnavailable, 2_000);
        };
        track.onunmute = () => {
          if (muteTimer) window.clearTimeout(muteTimer);
          muteTimer = null;
        };
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      const hasAudio = stream.getAudioTracks().some(
        (track) => track.readyState === "live" && track.enabled && !track.muted,
      );
      const hasVideo = stream.getVideoTracks().some(
        (track) => track.readyState === "live" && track.enabled && !track.muted,
      );
      if (!hasAudio || !hasVideo) {
        setError(
          hasAudio
            ? "Microfone ativo, mas a câmera não foi liberada. Verifique a permissão do navegador."
            : "Câmera ativa, mas o microfone não foi liberado. Verifique a permissão do navegador.",
        );
      }
      setMediaState(hasAudio && hasVideo ? "active" : "failed");
      if (hasAudio || hasVideo) {
        requestScreenWakeLock().then((lock) => {
          wakeLockRef.current = lock;
        });
      }
      // A captura acustica NAO pode depender de `!muted` num instante unico.
      // Uma trilha local de microfone reporta `muted` por um momento logo apos
      // o getUserMedia, e a janela em que este codigo roda e exatamente essa.
      // Quando calhava de coincidir, a captura nunca ligava, nunca tentava de
      // novo, e a sessao inteira era analisada sobre dados SIMULADOS sem que
      // ninguem soubesse — foi o que aconteceu em 02/09/2026.
      //
      // Para capturar basta a trilha existir e estar viva: o `muted`
      // transitorio se resolve sozinho e o worklet lida com silencio. O
      // criterio estrito continua valendo para a mensagem de permissao, que e
      // outra pergunta.
      const temTrilhaDeAudio = stream
        .getAudioTracks()
        .some((track) => track.readyState === "live");

      // Captura o microfone cru (pré-Opus) para o cálculo de F0 real no
      // backend. Aditivo e tolerante a falhas; não interfere na chamada.
      if (temTrilhaDeAudio && sessionId) {
        try {
          f0StopRef.current?.();
        } catch {
          /* noop */
        }
        f0StopRef.current = null;
        startF0Capture(stream, {
          endpoint: apiUrl(`/api/froid/${sessionId}/acoustic-f0`),
          invite: inviteToken,
          onStatus: (status, detalhe) => {
            registrarRtc(
              `analise acustica: ${STATUS_CAPTURA_TEXTO[status]}`
              + (detalhe ? ` (${detalhe})` : ""),
            );
            // Quem precisa saber disso e o profissional, e ele esta do outro
            // lado da sinalizacao. O paciente nao tem como reportar sozinho.
            const canal = rtcSignalRef.current;
            if (canal?.readyState === WebSocket.OPEN) {
              canal.send(JSON.stringify({ type: "acustica", status }));
            }
          },
        })
          .then((stop) => {
            if (streamRef.current === stream) f0StopRef.current = stop;
            else stop();
          })
          .catch(() => undefined);
      }
      // Captura facial real (blendshapes -> AUs FACS). Aditiva e tolerante a
      // falhas: se o modelo não carregar, o servidor mantém o modo simulado.
      if (hasVideo && sessionId) {
        try {
          faceStopRef.current?.();
        } catch {
          /* noop */
        }
        faceStopRef.current = null;
        startFaceCapture(stream, {
          endpoint: apiUrl(`/api/froid/${sessionId}/facial-aus`),
          invite: inviteToken,
        })
          .then((stop) => {
            if (streamRef.current === stream) faceStopRef.current = stop;
            else stop();
          })
          .catch(() => undefined);
      }
      await startPatientRtc(stream);
    } catch {
      setMediaState("failed");
      setError("Não foi possível ativar câmera e microfone neste navegador.");
    }
  };

  const statusText =
    joinState === "checking"
      ? copy.checking
      : joinState === "joined"
        ? copy.connected
        : copy.blocked;

  if (sessionEnded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-8 text-slate-100">
        <div className="w-full max-w-md rounded-xl border border-emerald-800 bg-slate-900 p-6 text-center shadow-lg">
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
            FROID
          </p>
          <h1 className="mt-2 text-xl font-bold text-slate-100">
            Sessão encerrada
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">
            Sua consulta foi encerrada pelo profissional. Você pode acompanhar
            os resultados e o histórico das suas sessões na sua área do
            paciente, quando quiser.
          </p>
          <button
            type="button"
            onClick={() => navigate("/paciente")}
            className="mt-5 inline-flex w-full items-center justify-center rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-bold text-white hover:bg-emerald-800"
          >
            Ir para minha área do paciente
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <main className="mx-auto max-w-4xl">
        <div className="mb-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
            FROID
          </p>
          <h1 className="mt-2 text-2xl font-bold">{copy.patientRoom}</h1>
          {uiLocale !== "pt-BR" && (
            <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-amber-300">
              {copy.pilotNotice}
            </p>
          )}
          <p className="mt-1 text-sm text-slate-400">
            {statusText}
            {patientName ? ` - ${patientName}` : ""}
          </p>
        </div>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-sm">
          <div className="relative aspect-video overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
            <video
              ref={remoteVideoRef}
              autoPlay
              playsInline
              muted
              className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
                remoteProfessionalVideoOn ? "opacity-100" : "opacity-0"
              }`}
            />
            <audio ref={remoteAudioRef} autoPlay className="hidden" />
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`absolute scale-x-[-1] object-cover transition-all duration-500 ${
                remoteProfessionalVideoOn
                  ? "bottom-3 right-3 z-20 h-24 w-36 rounded-lg border border-white/40 shadow-lg"
                  : "inset-0 h-full w-full"
              } ${mediaState === "active" ? "opacity-100" : "opacity-0"}`}
            />
            {mediaState !== "active" && (
              <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-slate-400">
                {copy.mediaPermission}
              </div>
            )}
            <div
              className={`absolute left-3 top-3 z-20 rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide backdrop-blur ${
                remoteProfessionalOn || remoteProfessionalVideoOn
                  ? "bg-emerald-500/90 text-white"
                  : "bg-slate-950/70 text-slate-200"
              }`}
            >
              {callStatus}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-slate-100">
                Sessão {sessionId}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                O profissional conduz a sessão pelo painel clínico FROID.
              </p>
            </div>
            <button
              type="button"
              onClick={activateMedia}
              disabled={joinState !== "joined" || mediaState === "requesting" || mediaState === "active"}
              className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mediaState === "requesting"
                ? copy.enablingMedia
                : mediaState === "active"
                  ? copy.mediaActive
                  : copy.enableMedia}
            </button>
          </div>

          {/* O QUE VAI ACONTECER, dito antes de acontecer.
              A tela pedia um toque num botao e nao explicava nada: nem que o
              navegador ia pedir permissao, nem que sem ela a sessao nao
              comeca, nem que depois disso nao ha mais nada a fazer. Quem nao
              sabe o que esperar interpreta a espera como defeito, fecha a
              pagina e reabre — e reabrir e justamente o que desconecta. */}
          {mediaState !== "active" && (
            <section className="mt-4 rounded-lg border border-cyan-900/60 bg-cyan-950/30 p-4">
              <p className="text-xs font-black uppercase tracking-wide text-cyan-200">
                {copy.howItWorksTitle}
              </p>
              <ol className="mt-3 space-y-2 text-xs leading-5 text-slate-200">
                <li className="flex gap-2">
                  <span className="font-black text-cyan-300">1.</span>
                  <span>{copy.howItWorksStep1}</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-black text-cyan-300">2.</span>
                  <span>{copy.howItWorksStep2}</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-black text-cyan-300">3.</span>
                  <span>{copy.howItWorksStep3}</span>
                </li>
              </ol>
              <p className="mt-3 border-t border-cyan-900/60 pt-3 text-xs leading-5 text-cyan-100">
                {copy.howItWorksOneDevice}
              </p>
            </section>
          )}

          {/* Aviso de reabertura. Nao bloqueia — o paciente pode ter fechado o
              outro aparelho legitimamente, e travar a entrada de quem tem
              direito a ela seria pior que o problema. */}
          {aberturasAnteriores > 0 && mediaState !== "active" && (
            <p className="mt-4 rounded-md border border-amber-800/60 bg-amber-950/40 px-3 py-2 text-xs leading-5 text-amber-100">
              {copy.alreadyOpenElsewhere}
            </p>
          )}

          {error && (
            <p className="mt-4 rounded-md border border-red-900/50 bg-red-950/50 px-3 py-2 text-xs font-semibold text-red-200">
              {error}
            </p>
          )}
        </section>
      </main>
    </div>
  );
};
