import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { STATUS_CAPTURA_TEXTO } from "./froid-acoustic";

const ler = (...partes: string[]) =>
  readFileSync(join(__dirname, "..", ...partes), "utf-8");

const ACUSTICA = ler("lib", "froid-acoustic.ts");
const PACIENTE = ler("pages", "PatientSessionPage.tsx");
const PROFISSIONAL = ler("pages", "LiveSession.tsx");
const AVISO = ler("components", "indicators", "AvisoVozSimulada.tsx");

/**
 * O defeito, vivido em 02/09/2026: uma sessão real de 24 minutos rodou inteira
 * com o motor em modo SIMULADO. `f0_mean` 0.00, `zcr` 0.000, derivadas
 * cepstrais zeradas — e o painel exibindo IPM, MFCC e índices DNA com a
 * aparência de sempre.
 *
 * A captura de PCM do paciente nunca ligou. `startF0Capture` engolia toda
 * exceção e devolvia uma função de parada vazia, indistinguível de sucesso; o
 * portão que a chamava exigia `!track.muted` num instante único, e uma trilha
 * local de microfone reporta `muted` por um momento logo após o getUserMedia.
 *
 * Nada em lugar nenhum dizia que a análise estava sobre dados gerados.
 */
describe("a captura acústica não pode mais fracassar em segredo", () => {
  it("todo estado possível tem texto legível", () => {
    const estados = [
      "sem-audio",
      "sem-suporte",
      "aguardando-gesto",
      "enviando",
      "sessao-inativa",
      "erro",
    ] as const;
    for (const estado of estados) {
      expect(STATUS_CAPTURA_TEXTO[estado]).toBeTruthy();
      expect(STATUS_CAPTURA_TEXTO[estado].length).toBeGreaterThan(10);
    }
  });

  it("«enviando» é o único estado que significa voz real", () => {
    // Se outro estado sugerisse sucesso, o aviso não apareceria justamente nas
    // sessões em que ele é necessário.
    const semSucesso = Object.entries(STATUS_CAPTURA_TEXTO)
      .filter(([chave]) => chave !== "enviando")
      .map(([, texto]) => texto);
    for (const texto of semSucesso) {
      expect(texto).not.toContain("enviando audio real");
    }
  });

  it("cada caminho de falha se anuncia", () => {
    for (const estado of ["sem-audio", "sem-suporte", "aguardando-gesto", "erro"]) {
      expect(ACUSTICA).toContain(`avisar("${estado}"`);
    }
  });

  it("o catch final relata a causa em vez de devolver função vazia", () => {
    // Era `catch { stop(); return () => {}; }` — o erro morria ali.
    expect(ACUSTICA).toContain("catch (erro) {");
    expect(ACUSTICA).not.toMatch(/\}\s*catch\s*\{\s*stop\(\);\s*return \(\) => \{\};/);
  });

  it("um AudioContext suspenso é declarado e religado no primeiro toque", () => {
    // Suspenso, o worklet NÃO roda e nenhum PCM sobe. Antes, "segue mesmo
    // assim" seguia para lugar nenhum.
    expect(ACUSTICA).toContain('avisar("aguardando-gesto")');
    expect(ACUSTICA).toContain('addEventListener("pointerdown", retomar)');
  });

  it("session_inactive não é tratado como sucesso", () => {
    // O servidor responde 200 com esse status quando a análise do profissional
    // ainda não abriu — nenhuma medida é produzida.
    expect(ACUSTICA).toContain('corpo.status === "session_inactive"');
    expect(ACUSTICA).toContain('avisar("sessao-inativa")');
  });
});

describe("a captura liga mesmo com a trilha momentaneamente muda", () => {
  it("o portão da captura NÃO exige !muted", () => {
    // A causa raiz. Para capturar basta a trilha existir e estar viva: o
    // `muted` transitório se resolve sozinho e o worklet lida com silêncio.
    expect(PACIENTE).toContain("const temTrilhaDeAudio = stream");
    expect(PACIENTE).toContain("if (temTrilhaDeAudio && sessionId) {");
  });

  it("o critério estrito continua valendo para a mensagem de permissão", () => {
    // São perguntas diferentes: "posso analisar?" e "o paciente liberou?".
    expect(PACIENTE).toContain("const hasAudio = stream.getAudioTracks().some(");
    expect(PACIENTE).toContain("!track.muted");
  });

  it("o estado da captura atravessa até o profissional", () => {
    // O paciente não tem painel nem suporte; quem precisa saber é quem conduz.
    expect(PACIENTE).toContain('type: "acustica"');
    expect(PROFISSIONAL).toContain('data.type === "acustica"');
  });
});

describe("voz simulada é dita na tela, não deduzida", () => {
  it("o aviso silencia quando a voz é real", () => {
    expect(AVISO).toContain('origem === "real_pcm"') ;
    expect(AVISO).toContain("return null");
  });

  it("o aviso diz o que NÃO vale, com nome", () => {
    expect(AVISO).toContain("F0, ZCR, MFCC");
    expect(AVISO).toContain("não use para leitura clínica");
  });

  it("o aviso diz o que continua válido — senão parece perda total", () => {
    expect(AVISO).toContain("transcrição");
  });

  it("a origem vem do MOTOR, não do navegador", () => {
    // O relato do paciente explica o porquê; quem tem autoridade sobre o que
    // entrou no cálculo é o servidor.
    expect(PROFISSIONAL).toContain("voice_features_source");
    expect(PROFISSIONAL).toContain("const origemDaVoz");
  });

  it("o aviso aparece nos dois layouts, não só num", () => {
    expect(PROFISSIONAL.match(/<AvisoVozSimulada /g)?.length).toBe(2);
  });
});

describe("o relatório declara a própria base probatória", () => {
  const RELATORIO = ler("pages", "SessionReport.tsx");
  const TIPO = ler("lib", "session-report.ts");

  /**
   * O que faltava: um relatório construído inteiramente sobre voz simulada era
   * indistinguível de um relatório clínico legítimo. Nenhum campo dizia que os
   * números tinham sido gerados em vez de medidos — nem para quem assina, nem
   * para quem recebe o documento depois.
   */

  it("a procedência é gravada no registro, amostra a amostra", () => {
    expect(TIPO).toContain("export interface ProcedenciaDosDados");
    expect(TIPO).toContain("amostrasComVozReal");
    expect(PROFISSIONAL).toContain("procedenciaDosDados: {");
    expect(PROFISSIONAL).toContain('=== "real_pcm"');
  });

  it("uma proporção, não um sim/não — sessão mista existe", () => {
    // Uma sessão pode ter os primeiros minutos simulados e o resto medido.
    // Reduzir isso a um booleano apagaria a diferença que importa.
    expect(RELATORIO).toContain("amostrasComVozReal / amostras");
    expect(RELATORIO).toContain("parcial");
  });

  it("zero amostras reais é dito com todas as letras", () => {
    expect(RELATORIO).toContain("não foram medidos");
    expect(RELATORIO).toContain("não devem ser lidos como");
  });

  it("relatório antigo diz «não sei», e não «foi medido»", () => {
    // Nem afirma que foi medido, nem que não foi: os anteriores a 02/09/2026
    // simplesmente não gravavam a origem.
    expect(RELATORIO).toContain("anterior ao registro de procedência");
  });

  it("a procedência vem ANTES dos números", () => {
    // Depois já é tarde: a leitura clínica do índice já aconteceu.
    expect(RELATORIO.indexOf("<ProcedenciaDoRelatorio")).toBeLessThan(
      RELATORIO.indexOf("{sections.evolution && activeMetricsAnalysis && ("),
    );
  });

  it("diz o que continua válido, para não parecer perda total", () => {
    expect(RELATORIO).toContain("não dependem desta origem e permanecem válidos");
  });
});
