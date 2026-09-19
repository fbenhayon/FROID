import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { sessaoComecou } from "./inicio-da-sessao";

/**
 * O relógio da sessão não conta espera.
 *
 * Relato do profissional em 19/09/2026: a sessão não abriu, ele esperou mais de
 * 2min30 com o cronômetro correndo e encerrou. O cronômetro estava certo sobre
 * o que media e errado sobre o que dizia: ele partia do microfone DELE, não da
 * chegada do paciente.
 *
 * O dano não é o número na tela. `elapsedSeconds` é o eixo de tempo de tudo o
 * que se mede — carimba cada amostra, delimita cada corte, abre a janela de
 * 60 s da baseline e vira a duração impressa no relatório. E `sessionStart`
 * dispara o encerramento automático aos 55 minutos, então cada minuto de espera
 * encurtava a consulta em um minuto.
 */

const NADA = {
  presencial: false,
  micOn: false,
  cameraOn: false,
  remotePatientOn: false,
  remotePatientVideoOn: false,
};

describe("no remoto, a sessão só começa com o paciente do outro lado", () => {
  it("microfone do profissional sozinho NÃO começa a sessão", () => {
    // O defeito, escrito como teste: era exatamente esta a condição antiga.
    expect(sessaoComecou({ ...NADA, micOn: true })).toBe(false);
  });

  it("câmera e microfone do profissional juntos também não", () => {
    expect(sessaoComecou({ ...NADA, micOn: true, cameraOn: true })).toBe(false);
  });

  it("começa quando o áudio do paciente chega", () => {
    expect(sessaoComecou({ ...NADA, micOn: true, remotePatientOn: true })).toBe(true);
  });

  it("começa também só com o vídeo dele", () => {
    // Paciente com microfone mudo ainda é uma sessão em curso.
    expect(sessaoComecou({ ...NADA, remotePatientVideoOn: true })).toBe(true);
  });

  it("sala vazia não começa nada", () => {
    expect(sessaoComecou(NADA)).toBe(false);
  });
});

describe("no presencial puro, esperar o paciente travaria o relógio para sempre", () => {
  // Não existe página do paciente nesse modo, logo não existe mídia dele. Exigi-la
  // seria o defeito simétrico: o relógio parado a consulta inteira.
  it("a captura local é a sessão", () => {
    expect(sessaoComecou({ ...NADA, presencial: true, micOn: true })).toBe(true);
  });

  it("sem captura nenhuma, ainda não começou", () => {
    expect(sessaoComecou({ ...NADA, presencial: true })).toBe(false);
  });
});

/**
 * O componente é de sete mil linhas e a regra do relógio vive fora dele, mas a
 * LIGAÇÃO entre os dois só se verifica aqui. Sem isto, a regra poderia estar
 * correta e não ser consultada por ninguém — o padrão desta casa.
 */
describe("o painel consome a regra em vez de reescrevê-la", () => {
  const LIVE = readFileSync(
    join(__dirname, "..", "pages", "LiveSession.tsx"),
    "utf-8",
  );

  it("a tela chama a regra", () => {
    expect(LIVE).toContain("sessaoComecou");
  });

  it("o relógio depende de a sessão ter começado, e não do microfone daqui", () => {
    const tick = LIVE.slice(LIVE.indexOf('case "TICK":'), LIVE.indexOf('case "SESSION_CONNECTED":'));
    expect(tick).toContain("state.clockStarted");
    expect(tick).not.toContain("state.micOn");
  });

  it("o cronômetro da tela parte do mesmo instante", () => {
    // `sessionStart` alimenta SessionTimer e o encerramento dos 55 minutos.
    // Escrevê-lo em MEDIA_STATUS era o que o amarrava ao microfone local.
    const media = LIVE.slice(
      LIVE.indexOf('case "MEDIA_STATUS":'),
      LIVE.indexOf('case "END_SESSION":'),
    );
    expect(media).not.toContain("sessionStart:");
    const conectada = LIVE.slice(
      LIVE.indexOf('case "SESSION_CONNECTED":'),
      LIVE.indexOf('case "PAYLOAD":'),
    );
    expect(conectada).toContain("sessionStart: Date.now()");
  });
});
