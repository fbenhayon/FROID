import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * O aviso que o servidor sempre mandou e ninguém nunca leu.
 *
 * `RtcSignalManager.relay` responde `{"type":"peer-waiting"}` quando alguém
 * envia sinal e o socket do outro lado não está na sala. Existe desde que a
 * sinalização existe. Nenhum dos dois clientes tinha ramo para essa mensagem —
 * ela caía fora de todos os `else if` e desaparecia.
 *
 * O efeito apareceu numa consulta real em 26/08/2026: a tela do profissional
 * ficou em "Chamando paciente..." indefinidamente, com o watchdog reofertando a
 * cada 8 segundos, enquanto o servidor repetia a cada volta que não havia
 * ninguém para receber a oferta. O profissional esperou uma conexão que não
 * tinha como acontecer, sem nada na tela que o dissesse.
 *
 * É a mesma família de "desenho completo, camada ausente" que já apareceu três
 * vezes neste repositório — só que aqui a camada ausente estava do lado que
 * ESCUTA, e não do lado que fala.
 */

const PROFISSIONAL = readFileSync(
  join(__dirname, "..", "pages", "LiveSession.tsx"),
  "utf-8",
);
const PACIENTE = readFileSync(
  join(__dirname, "..", "pages", "PatientSessionPage.tsx"),
  "utf-8",
);
const SERVIDOR = readFileSync(
  join(__dirname, "..", "..", "..", "froid-server", "main.py"),
  "utf-8",
);

describe("o servidor avisa quando não há par na sala", () => {
  it("o relay responde peer-waiting a quem sinalizou sozinho", () => {
    // Se este contrato mudar, os dois ramos abaixo viram código morto — e o
    // sintoma volta a ser uma tela que espera para sempre.
    expect(SERVIDOR).toContain('{"type": "peer-waiting"}');
  });
});

describe("os dois lados escutam o aviso", () => {
  it("o profissional trata peer-waiting", () => {
    expect(PROFISSIONAL).toContain('data.type === "peer-waiting"');
  });

  it("o paciente trata peer-waiting", () => {
    expect(PACIENTE).toContain('data.type === "peer-waiting"');
  });

  it("o profissional diz o que fazer, e não só o que houve", () => {
    // "O paciente não está na sala" sozinho deixa o profissional sem ação.
    const corrido = PROFISSIONAL.replace(/\s+/g, " ");
    expect(corrido).toMatch(/n[aã]o est[aá] na sala/i);
    expect(corrido).toMatch(/link do convite/i);
  });

  it("o paciente é instruído a manter a página aberta", () => {
    // A espera silenciosa fazia o paciente fechar a aba achando que o link
    // estava quebrado — e aí a sala esvaziava de verdade.
    const corrido = PACIENTE.replace(/\s+/g, " ");
    expect(corrido).toMatch(/deixe esta p[aá]gina aberta/i);
  });
});

describe("a oferta para de sair para uma sala vazia", () => {
  it("o watchdog é cancelado ao receber peer-waiting", () => {
    // Reofertar a cada 8s para ninguém não aproxima a conexão: só mantém a
    // mensagem errada na tela. A próxima oferta sai em `peer-joined`, que é o
    // evento que significa que existe alguém do outro lado.
    const i = PROFISSIONAL.indexOf('data.type === "peer-waiting"');
    const j = PROFISSIONAL.indexOf('data.type === "peer-left"', i);
    expect(i).toBeGreaterThan(-1);
    expect(PROFISSIONAL.slice(i, j)).toContain("clearOfferWatchdog()");
  });

  it("peer-joined continua sendo o gatilho da oferta", () => {
    // A chamada ganhou o argumento `true` logo depois desta trava nascer: quem
    // acaba de entrar tem prioridade sobre uma oferta que foi para a sala
    // vazia. O que importa aqui é que peer-joined OFERTE — a forma da chamada
    // é detalhe, e travar a grafia reprovaria a correção seguinte.
    expect(PROFISSIONAL).toContain('data.type === "peer-joined"');
    const i = PROFISSIONAL.indexOf('data.type === "peer-joined"');
    expect(PROFISSIONAL.slice(i, i + 400)).toMatch(/makeOffer\(/);
  });
});

/**
 * O impasse da oferta órfã.
 *
 * Observado na mesma consulta, logo depois do peer-waiting. A sequência:
 *
 *   1. o paciente cai; o peer do profissional vai para `failed`
 *   2. o tratamento de `failed` chama makeOffer, que fica em `have-local-offer`
 *      — e essa oferta vai para uma sala VAZIA
 *   3. o paciente volta; o servidor manda `peer-joined`
 *   4. o profissional chama makeOffer... e desiste em silêncio, porque
 *      `signalingState !== "stable"`
 *
 * Resultado: "Reconectando mídia do paciente..." de um lado e "Aguardando
 * chamada do profissional..." do outro, os dois esperando o outro, para
 * sempre.
 *
 * A guarda de estado está certa — ela evita colisão de ofertas. O que faltava
 * era distinguir a oferta que ainda pode ser respondida daquela que foi
 * entregue a ninguém. Quando o par ACABA de entrar, a pendente é sempre do
 * segundo tipo.
 */
describe("oferta pendente não pode travar quem acabou de entrar", () => {
  it("makeOffer aceita forçar", () => {
    expect(PROFISSIONAL).toContain("const makeOffer = async (forcar = false)");
  });

  it("forçar desfaz a oferta pendente com rollback", () => {
    const i = PROFISSIONAL.indexOf("const makeOffer = async (forcar = false)");
    const trecho = PROFISSIONAL.slice(i, i + 900);
    expect(trecho).toContain('setLocalDescription({ type: "rollback" })');
    expect(trecho).toContain('!== "have-local-offer"');
  });

  it("só força quando pedido — a guarda continua valendo por padrão", () => {
    // Sem a guarda, duas ofertas simultâneas colidem. O padrão continua sendo
    // desistir; forçar é a exceção de quem sabe que a sala mudou.
    const i = PROFISSIONAL.indexOf("const makeOffer = async (forcar = false)");
    expect(PROFISSIONAL.slice(i, i + 400)).toContain("if (!forcar");
  });

  it("peer-joined força a oferta", () => {
    const i = PROFISSIONAL.indexOf('data.type === "peer-joined"');
    expect(PROFISSIONAL.slice(i, i + 400)).toContain("makeOffer(true)");
  });

  it("renegotiate-request força a oferta — mas passando pelo freio", () => {
    // O recorte vai ate o proximo ramo em vez de contar caracteres: o bloco
    // cresceu quando o freio entrou, e um numero magico quebra a cada
    // comentario acrescentado sem que nada de fato tenha regredido.
    const i = PROFISSIONAL.indexOf('data.type === "renegotiate-request"');
    const fim = PROFISSIONAL.indexOf("} else if (data.type", i);
    const ramo = PROFISSIONAL.slice(i, fim > 0 ? fim : i + 900);
    expect(ramo).toContain("makeOffer(true)");
    // O laço de 02/09/2026: sem limite, cada pedido virava outra oferta, e o
    // ICE era reiniciado antes de chegar a `checking` uma única vez.
    expect(ramo).toContain("freioRenegociacao.permite()");
  });
});

describe("o paciente deixa de ser passivo", () => {
  it("trata signal-ready e peer-joined", () => {
    // Ele tratava offer, ice, peer-left e session-ended, e mais nada. As duas
    // mensagens que dizem "o profissional está aí" passavam batidas.
    expect(PACIENTE).toContain('data.type === "signal-ready"');
    expect(PACIENTE).toContain('data.type === "peer-joined"');
  });

  it("pede a chamada quando o profissional já está na sala", () => {
    // Quem sabe que acabou de entrar é o paciente. Pedir daqui é o que tira os
    // dois do impasse quando o peer-joined do outro lado se perde.
    const i = PACIENTE.indexOf('data.type === "signal-ready"');
    const trecho = PACIENTE.slice(i, i + 700);
    expect(trecho).toContain('sendSignal({ type: "renegotiate-request" })');
    expect(trecho).toContain("peer_connected");
  });

  it("não pede nada quando está sozinho na sala", () => {
    const i = PACIENTE.indexOf('data.type === "signal-ready"');
    expect(PACIENTE.slice(i, i + 700)).toMatch(/Aguardando chamada do profissional/);
  });
});

/**
 * A invisibilidade que definiu o incidente.
 *
 * O paciente precisa TOCAR "Ativar câmera e microfone" e conceder permissão
 * antes que o socket de sinalização abra — `startPatientRtc` só é chamado
 * dentro de `activateMedia`, depois do `getUserMedia`. Durante todo esse tempo
 * o profissional lê "Aguardando paciente..." e não consegue distinguir quatro
 * situações que pedem ações opostas: o paciente não abriu o link; abriu e não
 * tocou o botão; tocou e está olhando o pedido de permissão; negou a permissão.
 *
 * Em três das quatro a ação certa é falar com o paciente, não esperar.
 *
 * O servidor já sabia: registra `invite_opened`, `invite_accepted` e
 * `patient_joined`, e publica em /api/session-events. Dashboard.tsx consome há
 * meses. A tela da sessão — único lugar onde a informação decide algo — não
 * consumia.
 */
describe("o profissional enxerga onde o paciente está", () => {
  it("a tela da sessão consome os eventos de presença", () => {
    expect(PROFISSIONAL).toContain("/api/session-events?after=");
  });

  it("distingue os três passos do paciente", () => {
    const corrido = PROFISSIONAL.replace(/\s+/g, " ");
    expect(corrido).toMatch(/abriu o link do convite/i);
    expect(corrido).toMatch(/confirmou o cadastro/i);
    expect(corrido).toMatch(/liberar c[âa]mera e microfone no pr[óo]prio aparelho/i);
  });

  it("filtra pelos eventos DESTA sessão", () => {
    // O profissional pode ter outros convites abertos. Presença de outro
    // paciente nesta tela seria pior que silêncio.
    expect(PROFISSIONAL).toContain("String(evento.session_id || \"\") === sessionId");
  });

  it("a presença não sobrescreve o estado da negociação", () => {
    // São duas máquinas diferentes: rtcStatus descreve o WebRTC, presença
    // descreve a pessoa. Misturá-las cria corrida entre quem escreve por último.
    expect(PROFISSIONAL).toContain("setPresencaDoPaciente");
    const i = PROFISSIONAL.indexOf("const perguntar = async ()");
    const j = PROFISSIONAL.indexOf("window.setInterval(perguntar", i);
    expect(PROFISSIONAL.slice(i, j)).not.toContain("setRtcStatus");
  });

  it("para de perguntar quando a mídia chega", () => {
    // A partir daí quem descreve a sessão é o próprio vídeo.
    const i = PROFISSIONAL.indexOf("/api/session-events?after=");
    const inicio = PROFISSIONAL.lastIndexOf("useEffect(() => {", i);
    expect(PROFISSIONAL.slice(inicio, i)).toContain(
      "if (remotePatientOn || remotePatientVideoOn) return;",
    );
  });

  it("falha ao buscar presença não atrapalha a sessão", () => {
    const i = PROFISSIONAL.indexOf("const perguntar = async ()");
    const j = PROFISSIONAL.indexOf("void perguntar()", i);
    expect(PROFISSIONAL.slice(i, j)).toContain("} catch {");
  });
});

describe("a credencial de TURN sai do caminho crítico", () => {
  it("o paciente busca a configuração ao entrar, não ao tocar o botão", () => {
    // Buscar em activateMedia deixa a requisição correndo junto com o pedido
    // de permissão, que é o trecho lento. Buscar na montagem faz o
    // RTCPeerConnection nascer com a configuração já em cache.
    const i = PACIENTE.indexOf('joinState !== "joined"');
    expect(i).toBeGreaterThan(-1);
    expect(PACIENTE.slice(i, i + 260)).toContain("loadRtcConfiguration");
  });
});
