// Contrato do motor facial único. Nenhuma regra emocional é executada aqui.
export interface FacialFamily {
  id: string;
  title: string;
  description: string;
  status: "candidate" | "observed" | "not_detected" | "unavailable";
  confirmed: boolean;
  variants: Array<{ id: string; aus: string[]; side: string | null }>;
}

export interface FacialEvent {
  id: string;
  schema_version: "facial_families_v1";
  family: string;
  title: string;
  report: string;
  patient_title: string;
  patient_description: string;
  variant: string;
  active_aus: string[];
  side: string | null;
  started_at_ms: number;
  last_observed_at_ms: number;
  ended_at_ms: number | null;
  observations: number;
  confirmed: boolean;
  ambiguous: boolean;
  strength: number;
  peak_strength: number;
  action_units: Record<string, number | null>;
  lateral: Record<string, { left: number | null; right: number | null }>;
  source: "real_facs";
  clinical_confidence: null;
  /** Tempo de recepção no painel, não duração/início da expressão. */
  recorded_elapsed_seconds?: number;
  /** Afastamento de cada AU da variante em relação à referência individual
   *  (modo de medição). null = sem referência ou AU não medida. */
  baseline_delta?: Record<string, number | null>;
  peak_baseline_delta?: number | null;
  baseline_status?: FacialBaselineSummary["status"];
}

/** Referência facial individual dos 60 s iniciais — MODO DE MEDIÇÃO.
 *  Não filtra nem classifica padrões; `threshold` fica null até que o limiar
 *  seja escolhido a partir de sessões reais. */
export interface FacialBaselineSummary {
  schema_version: "facial_baseline_v1";
  mode: "measurement_only";
  status: "waiting" | "calibrating" | "ready" | "insufficient";
  window_s: number;
  min_frames: number;
  calibration_frames: number;
  frames_after_calibration: number;
  reference: Record<string, { median: number; scale: number; frames: number } | null> | null;
  deviation: Record<string, { frames: number; p50?: number; p90?: number; p95?: number; p99?: number; max: number | null } | null> | null;
  threshold: number | null;
  threshold_reason: string;
}

export interface FacialAnalysis {
  schema_version: "facial_families_v1";
  status: "measured" | "unavailable";
  reason: string | null;
  families: FacialFamily[];
  action_units: Record<string, number | null> | null;
  lateral: Record<string, { left: number | null; right: number | null }>;
  raw_blendshapes: Record<string, number>;
  legacy_estimates: Record<string, number | null>;
  ambiguous: boolean;
  limitations: string[];
  observed_at_ms?: number;
  expires_at_ms?: number;
  dissonance: { status: "unavailable"; reason: string };
  facial_baseline?: FacialBaselineSummary;
}

export function mergeFacialEvents(previous: FacialEvent[], incoming: FacialEvent[]): FacialEvent[] {
  const entries = new Map(previous.map(event => [event.id, event]));
  for (const event of incoming) {
    if (event.schema_version === "facial_families_v1" && event.confirmed && event.source === "real_facs") {
      const existing = entries.get(event.id);
      if (!existing || event.last_observed_at_ms >= existing.last_observed_at_ms) {
        entries.set(event.id, { ...event,
          recorded_elapsed_seconds: existing?.recorded_elapsed_seconds ?? event.recorded_elapsed_seconds });
      }
    }
  }
  return [...entries.values()];
}

// RELATÓRIO POR CORTE (decisão do dono, 08/11/2026).
//
// O relatório mostrava, nos sete cartões, a fotografia do ÚLTIMO instante da
// sessão. No último segundo quase nunca há expressão, então os cartões diziam
// "não detectado" enquanto o registro, recolhido ao pé, tinha 25 padrões.
// Agora o relatório distribui os eventos pelos cortes, pelo segundo da sessão
// em que cada um chegou ao painel (`recorded_elapsed_seconds`). Evento sem esse
// segundo NÃO é encaixado por estimativa: vai para "sem horário na sessão".
export interface FacialCutGroup {
  startSecond: number;
  endSecond: number;
  events: FacialEvent[];
}

export interface FacialEventsByCut {
  cuts: FacialCutGroup[];
  /** Têm segundo da sessão, mas ele não cai em nenhum corte registrado. */
  outsideCuts: FacialEvent[];
  /** Relatórios antigos: sem segundo da sessão, não há corte a atribuir. */
  withoutTime: FacialEvent[];
}

function elapsedOf(event: FacialEvent): number | null {
  const t = event.recorded_elapsed_seconds;
  return typeof t === "number" && Number.isFinite(t) ? t : null;
}

export function groupFacialEventsByCut(
  events: FacialEvent[],
  cuts: Array<{ startSecond: number; endSecond: number }>,
): FacialEventsByCut {
  const groups: FacialCutGroup[] = (cuts || [])
    .filter(c => Number.isFinite(c.startSecond) && Number.isFinite(c.endSecond) && c.endSecond > c.startSecond)
    .sort((a, b) => a.startSecond - b.startSecond)
    .map(c => ({ startSecond: c.startSecond, endSecond: c.endSecond, events: [] }));
  const outsideCuts: FacialEvent[] = [];
  const withoutTime: FacialEvent[] = [];
  const ordered = [...(events || [])].sort((a, b) =>
    (elapsedOf(a) ?? Infinity) - (elapsedOf(b) ?? Infinity) || a.started_at_ms - b.started_at_ms);
  const last = groups.length - 1;
  for (const event of ordered) {
    const t = elapsedOf(event);
    if (t === null) { withoutTime.push(event); continue; }
    const group = groups.find((c, i) => t >= c.startSecond && (t < c.endSecond || (i === last && t <= c.endSecond)));
    if (group) group.events.push(event); else outsideCuts.push(event);
  }
  return { cuts: groups, outsideCuts, withoutTime };
}

/** A fala no instante do evento: a última linha dita até aquele segundo.
 *  Mesma regra de `transcricaoParaOExplica`: sem a lista de segundos, ou com
 *  tamanho diferente do de linhas, nada é inferido e a resposta é null. */
export function speechAtSecond(
  transcript: string | undefined,
  secondsPerLine: number[] | undefined,
  second: number,
): string | null {
  const lines = String(transcript || "").split("\n");
  if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
  const seconds = Array.isArray(secondsPerLine) ? secondsPerLine : [];
  if (!lines.length || seconds.length !== lines.length || !seconds.every(s => Number.isFinite(s))) return null;
  let best = -1;
  for (let i = 0; i < lines.length; i++) {
    if (seconds[i] <= second && lines[i].trim() && (best < 0 || seconds[i] >= seconds[best])) best = i;
  }
  if (best < 0) return null;
  const line = lines[best].trim();
  return line.length > 180 ? `${line.slice(0, 177)}…` : line;
}

export function mmss(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

// O FROID EXPLICA NÃO RECEBIA O ROSTO (08/11/2026).
//
// O contexto do relatório levava métricas, cortes e transcrição, e nenhum
// evento facial: "o que o rosto fez no corte 2?" não tinha como ser
// respondido. Este produtor manda o mesmo agrupamento que a tela mostra, em
// texto compacto, com teto declarado — nunca cortado em silêncio.
export const LIMITE_EVENTOS_FACIAIS_NO_EXPLICA = 150;

export function contextoFacialParaOExplica(input: {
  events: FacialEvent[];
  cuts: Array<{ startSecond: number; endSecond: number }>;
  analysis?: FacialAnalysis;
  procedencia?: { amostras: number; amostrasComFaceReal: number };
}): Record<string, unknown> {
  const { events, cuts, analysis, procedencia } = input;
  const grouped = groupFacialEventsByCut(events || [], cuts || []);
  let usados = 0;
  let omitidos = 0;
  const linha = (e: FacialEvent) => {
    if (usados >= LIMITE_EVENTOS_FACIAIS_NO_EXPLICA) { omitidos++; return null; }
    usados++;
    const t = e.recorded_elapsed_seconds;
    const quando = typeof t === "number" && Number.isFinite(t) ? mmss(t) : "sem instante";
    const fim = e.ended_at_ms ?? e.last_observed_at_ms;
    const dur = Number.isFinite(fim) && fim >= e.started_at_ms ? `, ${((fim - e.started_at_ms) / 1000).toFixed(1)} s` : "";
    const pico = typeof e.peak_baseline_delta === "number"
      ? `, afastamento de pico da referencia ${e.peak_baseline_delta >= 0 ? "+" : ""}${e.peak_baseline_delta.toFixed(2)}`
      : "";
    return `${quando} ${e.title} (${e.observations} quadros${dur}${pico})`;
  };
  const bloco = (list: FacialEvent[]) => list.map(linha).filter((x): x is string => !!x);
  const total = procedencia?.amostras;
  const face = procedencia?.amostrasComFaceReal;
  const b = analysis?.facial_baseline;
  return {
    report_facial_by_cut: {
      leitura: "Eventos faciais confirmados (padrao repetido em quadros distintos), por corte, no instante da sessao em que chegaram ao painel. Sao descritivos: nao comprovam emocao, mentira nem dissonancia facial-vocal, que nao e apurada.",
      captura: typeof total === "number" && typeof face === "number" && total > 0
        ? `leitura facial real em ${face} de ${total} amostras (${Math.round((face / total) * 100)}%)`
        : "sem capacidade de apuracao neste relatorio",
      referencia_individual: !b ? "nao registrada neste relatorio (anterior a calibracao facial)"
        : b.status === "ready" ? `calibrada com ${b.calibration_frames} quadros nos ${b.window_s} s iniciais; modo de medicao: ainda nao filtra os padroes; limiar ainda nao definido`
        : b.status === "insufficient" ? `insuficiente: ${b.calibration_frames} quadros (minimo ${b.min_frames}); afastamentos nao apurados`
        : "calibracao nao concluida nesta sessao",
      cortes: grouped.cuts.map((c, i) => {
        const itens = bloco(c.events);
        return `Corte ${i + 1} ${mmss(c.startSecond)}-${mmss(c.endSecond)}: ${itens.length ? itens.join("; ") : c.events.length ? "eventos omitidos pelo teto" : "nenhum padrao facial registrado"}`;
      }),
      ...(grouped.outsideCuts.length ? { fora_dos_cortes: bloco(grouped.outsideCuts) } : {}),
      ...(grouped.withoutTime.length ? { sem_instante_na_sessao: bloco(grouped.withoutTime) } : {}),
      ...(omitidos ? { truncado: `${omitidos} eventos alem do teto de ${LIMITE_EVENTOS_FACIAIS_NO_EXPLICA} nao foram enviados; se a pergunta depender deles, diga que nao vieram` } : {}),
    },
  };
}

/** Expiração é validade de transporte, não uma nova interpretação facial. */
export function currentFacialAnalysis(analysis?: FacialAnalysis, now = Date.now()): FacialAnalysis | undefined {
  if (!analysis || analysis.expires_at_ms === undefined || now <= analysis.expires_at_ms) return analysis;
  return { ...analysis, status: "unavailable", action_units: null, raw_blendshapes: {}, legacy_estimates: {},
    lateral: {}, ambiguous: false, reason: "Leitura facial vencida; sem capacidade de apuração atual.",
    families: analysis.families.map(family => ({ ...family, status: "unavailable", confirmed: false, variants: [] })) };
}
