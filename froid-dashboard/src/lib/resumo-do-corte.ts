import type { MetricSnapshot, SessionReportRecord } from "./session-report";

/**
 * Casamento entre um corte (métricas) e o resumo de conversa daquele corte.
 *
 * Viviam dentro de `SessionReport.tsx`, e só a página de relatório os usava.
 * Em 15/10/2026 o FROID Explica passou a receber uma tabela compacta por
 * corte, com tema e resumo ao lado das métricas, e a ficha do paciente precisa
 * do mesmo casamento. Uma segunda cópia da regra de sobreposição divergiria
 * em silêncio na primeira mudança — então a regra mora aqui, uma vez.
 */
export type ResumoDoCorte = SessionReportRecord["conversationSummaries"][number];

export function secondsForSummary(summary: ResumoDoCorte) {
  return {
    start: Math.max(0, Math.floor(summary.startSecond ?? summary.startMinute * 60)),
    end: Math.max(
      Math.floor(summary.startSecond ?? summary.startMinute * 60) + 1,
      Math.ceil(summary.endSecond ?? summary.endMinute * 60),
    ),
  };
}

export function overlapSeconds(
  leftStart: number,
  leftEnd: number,
  rightStart: number,
  rightEnd: number,
) {
  return Math.max(0, Math.min(leftEnd, rightEnd) - Math.max(leftStart, rightStart));
}

export function findCutForSummary(
  summary: ResumoDoCorte,
  cuts: MetricSnapshot[],
): MetricSnapshot | undefined {
  const interval = secondsForSummary(summary);
  const best = [...cuts]
    .map((cut) => ({
      cut,
      overlap: overlapSeconds(
        interval.start,
        interval.end,
        cut.startSecond,
        cut.endSecond,
      ),
    }))
    .sort((a, b) => b.overlap - a.overlap)[0];
  return best?.overlap ? best.cut : undefined;
}

export function findSummaryForCut(
  cut: MetricSnapshot,
  summaries: ResumoDoCorte[],
): ResumoDoCorte | undefined {
  const best = [...summaries]
    .map((summary) => {
      const interval = secondsForSummary(summary);
      return {
        summary,
        overlap: overlapSeconds(
          cut.startSecond,
          cut.endSecond,
          interval.start,
          interval.end,
        ),
      };
    })
    .sort((a, b) => b.overlap - a.overlap)[0];
  return best?.overlap ? best.summary : undefined;
}
