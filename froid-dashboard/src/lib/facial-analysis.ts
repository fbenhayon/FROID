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

/** Expiração é validade de transporte, não uma nova interpretação facial. */
export function currentFacialAnalysis(analysis?: FacialAnalysis, now = Date.now()): FacialAnalysis | undefined {
  if (!analysis || analysis.expires_at_ms === undefined || now <= analysis.expires_at_ms) return analysis;
  return { ...analysis, status: "unavailable", action_units: null, raw_blendshapes: {}, legacy_estimates: {},
    lateral: {}, ambiguous: false, reason: "Leitura facial vencida; sem capacidade de apuração atual.",
    families: analysis.families.map(family => ({ ...family, status: "unavailable", confirmed: false, variants: [] })) };
}
