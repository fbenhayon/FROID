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
    expect(PROFISSIONAL).toContain('data.type === "peer-joined"');
    const i = PROFISSIONAL.indexOf('data.type === "peer-joined"');
    expect(PROFISSIONAL.slice(i, i + 200)).toContain("makeOffer()");
  });
});
