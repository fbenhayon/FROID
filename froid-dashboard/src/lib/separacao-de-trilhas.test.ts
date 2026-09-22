import { readFileSync } from "node:fs";
import ts from "typescript";
import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("../pages/LiveSession.tsx", import.meta.url), "utf8");
const tree = ts.createSourceFile("LiveSession.tsx", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
function expression(name: string) {
  const matches: string[] = [];
  function visit(node: ts.Node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(tree) === name && node.initializer) {
      matches.push(node.initializer.getText(tree));
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  expect(matches).toHaveLength(1);
  return matches[0];
}
function evaluate(name: string, context: Record<string, unknown>) {
  return new Function(...Object.keys(context), `return (${expression(name)});`)(...Object.values(context));
}

describe("origem da fala durante perda da trilha remota", () => {
  it.each([true, false])("profissional permanece DR com remoto ativo=%s", (remoteActive) => {
    const context = { source: "professional", isPresentialSession: false,
      remotePatientOnRef: { current: remoteActive }, attributedSpeakerRef: { current: "PC" },
      forcedLocalSegmentSpeakerRef: { current: "PC" }, speaker: "DR" };
    const forcedSpeaker = evaluate("forcedSpeaker", context);
    expect(evaluate("segmentSpeaker", { ...context, forcedSpeaker })).toBe("DR");
  });
  it("paciente permanece PC mesmo com atribuicao local DR", () => {
    const context = { source: "patient", isPresentialSession: false,
      attributedSpeakerRef: { current: "DR" }, forcedLocalSegmentSpeakerRef: { current: "DR" }, speaker: "PC" };
    expect(evaluate("segmentSpeaker", { ...context, forcedSpeaker: evaluate("forcedSpeaker", context) })).toBe("PC");
  });
  it("microfone compartilhado sem identificacao nao vira paciente", () => {
    expect(evaluate("metricSpeaker", { hasAutomaticVoiceGuard: false, speakerIdMode: "auto", attributedSpeaker: "PC" })).toBeNull();
  });
  it.each(["PC", "DR"])("respeita selecao manual presencial %s", (speaker) => {
    expect(evaluate("metricSpeaker", { hasAutomaticVoiceGuard: false, speakerIdMode: "manual", attributedSpeaker: speaker })).toBe(speaker);
  });
});
