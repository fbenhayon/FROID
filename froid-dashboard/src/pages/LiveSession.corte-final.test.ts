import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * O corte final, e por que ele não existia.
 *
 * O corte semântico fecha a cada dez minutos. O trecho falado DEPOIS do último
 * corte automático nunca era fechado: o gatilho "final" existia no tipo e no
 * construtor do relatório, e nada o chamava. Numa sessão de 50 minutos isso
 * descartava os últimos dez; numa de 8 minutos, a sessão inteira. Conteúdo
 * clínico perdido em silêncio, sem erro na tela.
 *
 * A segunda camada do defeito era mais sutil: createSessionReport lia os cortes
 * do ESTADO do React, enquanto lia todo o resto de refs. Um corte fechado no
 * mesmo tique do encerramento não chegaria ao relatório, porque a atualização
 * de estado só vale no render seguinte — que nunca acontece, já que a sessão
 * acabou. Chamar o corte final sem corrigir isso teria dado a impressão de
 * conserto sem consertar nada.
 */

const FONTE = readFileSync(join(__dirname, "LiveSession.tsx"), "utf-8");
/** Espaço em branco colapsado, para procurar frase sem depender de indentação
 *  nem de o arquivo estar em CRLF — as duas coisas já reprovaram código correto
 *  em testes meus antes deste. */
const CORRIDO = FONTE.replace(/\s+/g, " ");

function trecho(inicio: string, fim: string): string {
  const i = FONTE.indexOf(inicio);
  expect(i, `âncora ausente: ${inicio}`).toBeGreaterThan(-1);
  const f = FONTE.indexOf(fim, i + inicio.length);
  expect(f, `fim ausente após ${inicio}`).toBeGreaterThan(i);
  return FONTE.slice(i, f);
}

describe("o encerramento fecha o trecho residual", () => {
  const encerramento = trecho("const endSession = useCallback", "const report = createSessionReport()");

  it("chama o corte final", () => {
    expect(encerramento).toContain('closeSemanticCut("final")');
  });

  it("fecha o corte ANTES de montar o relatório", () => {
    // A ordem é o conserto inteiro: depois de montado, o relatório já foi.
    const posCorte = FONTE.indexOf('await closeSemanticCut("final")');
    const posRelatorio = FONTE.indexOf("const report = createSessionReport()");
    expect(posCorte).toBeGreaterThan(-1);
    expect(posCorte).toBeLessThan(posRelatorio);
  });

  it("uma falha no corte não impede o arquivamento", () => {
    // Sessão realizada nunca é recusada nem descartada — a mesma regra que já
    // vale para crédito. O relatório carrega a transcrição completa mesmo sem
    // o corte, então perder o corte é ruim e perder o atendimento seria pior.
    expect(encerramento).toMatch(/try\s*\{\s*await closeSemanticCut\("final"\)/);
    expect(encerramento).toContain("catch");
  });
});

describe("o relatório enxerga o corte recém-fechado", () => {
  it("os cortes vêm do ref, não do estado", () => {
    const construtor = trecho("const createSessionReport = useCallback", "const anonymizedContext");
    expect(construtor).toContain("conversationSummariesRef.current");
  });

  it("o corpo do relatório também usa o ref", () => {
    expect(FONTE).toContain("conversationSummaries: conversationSummariesRef.current");
    expect(CORRIDO).toContain("buildSessionSummary( conversationSummariesRef.current,");
  });

  it("o ref é atualizado de forma síncrona ao gravar um corte", () => {
    const commit = trecho("const commitSummary =", "if (!transcript)");
    expect(commit).toContain("conversationSummariesRef.current =");
    expect(commit).toContain("setConversationSummaries(conversationSummariesRef.current)");
  });
});

describe("as arestas do corte final", () => {
  const fechamento = trecho("async (trigger: \"automatico_10min\"", "semanticCutClosingRef.current = true");

  it("o final espera um corte automático em voo, em vez de desistir", () => {
    // Desistir aqui devolveria exatamente o defeito que este corte fecha.
    expect(fechamento).toContain('if (trigger !== "final") return;');
    expect(fechamento).toMatch(/while \(semanticCutClosingRef\.current/);
  });

  it("a espera tem limite", () => {
    // Travar o encerramento seria pior do que um corte a menos.
    expect(fechamento).toMatch(/Date\.now\(\) \+ \d+/);
  });

  it("não cria corte de duração zero", () => {
    expect(fechamento).toContain('if (trigger === "final" && duration < 1)');
  });
});

describe("os dois caminhos de encerramento", () => {
  it("o botão e o fim do tempo passam pelo mesmo lugar", () => {
    // Se algum dia o encerramento por tempo ganhar caminho próprio, ele volta a
    // perder o trecho residual sem ninguém notar.
    expect(FONTE).toContain("onClick={endSession}");
    expect(FONTE).toContain("onEndSession={endSession}");
  });
});
