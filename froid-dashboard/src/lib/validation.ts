/**
 * Estudo de validade convergente — acesso e vocabulário compartilhados.
 *
 * O FROID não aplica nem pontua o questionário: o profissional aplica o PHQ-9
 * e registra a pontuação. Nada aqui renderiza item de instrumento, e essa
 * ausência é deliberada — é o que mantém o produto como instrumentação e fora
 * da definição de instrumento de avaliação psicológica.
 */
import { apiUrl } from "./api";

export const PILOT_PAIRS = 30;
export const TARGET_PAIRS = 70;

/** O único instrumento do estágio 1. Dois por sessão é onde a adesão morre. */
export const INSTRUMENT = "PHQ-9";
export const INSTRUMENT_MAX = 27;

export type ConsentState = "granted" | "revoked" | "never_asked";

export type ConsentInfo = {
  state: ConsentState;
  version: string | null;
  at: string | null;
};

export type Administration = {
  administered_at: string;
  instrument: string;
  total_score: number;
  score_max: number;
  session_id: string | null;
  patterns: number;
};

export type Hypothesis = {
  pattern_key: string;
  instrument: string;
  expected_direction: number;
  pairs: number;
};

export type ValidationResult = {
  pattern_key: string;
  instrument: string;
  expected_direction: number;
  n: number;
  progress: string;
  is_final: boolean;
  r: number | null;
  interval: [number, number] | null;
  verdict: string;
  detail: string;
  statement: string;
};

/**
 * Nome legível do padrão. Nenhum deles nomeia condição clínica.
 *
 * Não exportado de propósito: quem precisa do rótulo usa `patternLabel`, que
 * tem fallback para a chave. Exportar o mapa convidaria a um acesso direto que
 * quebra quando a chave não existe.
 */
const PATTERN_LABELS: Record<string, string> = {
  psychomotor_slowing: "Lentificação psicomotora vocal",
  prosodic_activation: "Ativação prosódica",
  laryngeal_tension: "Tensão laríngea sustentada",
};

export const VERDICT_LABELS: Record<string, string> = {
  insufficient_sample: "Amostra insuficiente",
  unusable_sample: "Amostra inutilizável",
  inconclusive: "Inconclusivo",
  contradicted: "Contradiz a hipótese",
  negligible: "Desprezível",
  weak: "Fraco",
  moderate: "Moderado",
  strong: "Forte",
};

export function patternLabel(key: string) {
  return PATTERN_LABELS[key] || key;
}

/**
 * Organização ativa, para telas que não recebem `user` por prop.
 *
 * Sem organização, os componentes de validade não renderizam — nunca chutam
 * um tenant. Consulta sem escopo em dado de paciente é o defeito que a RLS
 * existe para impedir, e a tela não deve ser a camada que o introduz.
 */
export function activeOrganizationId(): string {
  if (typeof window === "undefined") return "";
  try {
    const stored = JSON.parse(window.localStorage.getItem("froid_user") || "{}");
    return (
      stored.active_organization_id ||
      stored.organizations?.[0]?.organization_id ||
      ""
    );
  } catch {
    return "";
  }
}

export function authHeaders(organizationId: string) {
  const token = window.localStorage.getItem("froid_token") || "";
  return {
    Authorization: `Bearer ${token}`,
    "X-FROID-Organization-ID": organizationId,
  };
}

async function readJson(response: Response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data?.detail || "Falha na requisição.");
  }
  return data;
}

export async function fetchConsent(organizationId: string, patientId: string) {
  const response = await fetch(
    apiUrl(`/api/organizations/${organizationId}/validation/consent/${patientId}`),
    { headers: authHeaders(organizationId) },
  );
  return (await readJson(response)) as ConsentInfo;
}

export async function setConsent(
  organizationId: string,
  patientId: string,
  granted: boolean,
) {
  const response = await fetch(
    apiUrl(`/api/organizations/${organizationId}/validation/consent/${patientId}`),
    {
      method: "POST",
      headers: { ...authHeaders(organizationId), "Content-Type": "application/json" },
      body: JSON.stringify({ granted }),
    },
  );
  return (await readJson(response)) as {
    granted: boolean;
    removed_administrations: number;
  };
}

export async function fetchPatientValidation(
  organizationId: string,
  patientId: string,
) {
  const response = await fetch(
    apiUrl(`/api/organizations/${organizationId}/validation/patients/${patientId}`),
    { headers: authHeaders(organizationId) },
  );
  return (await readJson(response)) as {
    consent: ConsentInfo;
    administrations: Administration[];
  };
}

export async function recordAdministration(
  organizationId: string,
  payload: {
    patient_id: string;
    total_score: number;
    session_id?: string | null;
    administered_at?: string;
    observations?: Array<Record<string, unknown>>;
  },
) {
  const response = await fetch(
    apiUrl(`/api/organizations/${organizationId}/validation/administrations`),
    {
      method: "POST",
      headers: { ...authHeaders(organizationId), "Content-Type": "application/json" },
      body: JSON.stringify({ instrument: INSTRUMENT, ...payload }),
    },
  );
  return (await readJson(response)) as { administration_id: string };
}

export async function fetchProgress(organizationId: string) {
  const response = await fetch(
    apiUrl(`/api/organizations/${organizationId}/validation/progress`),
    { headers: authHeaders(organizationId) },
  );
  return (await readJson(response)) as {
    target: number;
    pilot: number;
    floor: number;
    /** Falso enquanto não houver parecer do CEP registrado. */
    collection_allowed: boolean;
    ethics_approval: string;
    hypotheses: Hypothesis[];
  };
}

/**
 * A coleta está liberada pelo comitê de ética?
 *
 * As telas de coleta consultam isto antes de aparecer. Oferecer um campo que
 * o backend vai recusar treina o profissional a ignorar mensagem de erro, e
 * pior: sugere que a pesquisa já começou quando ela ainda não pode começar.
 */
export async function collectionAllowed(organizationId: string) {
  try {
    const data = await fetchProgress(organizationId);
    return Boolean(data.collection_allowed);
  } catch {
    return false;
  }
}

export async function fetchReport(organizationId: string) {
  const response = await fetch(
    apiUrl(`/api/organizations/${organizationId}/validation/report`),
    { headers: authHeaders(organizationId) },
  );
  return (await readJson(response)) as {
    target: number;
    results: ValidationResult[];
  };
}

/**
 * O marco imediato: o piloto até fechar, depois o confirmatório.
 *
 * Mostrar sempre 70 faria o profissional olhar uma barra que quase não anda
 * durante meses. Mostrar o marco seguinte mantém o progresso legível sem
 * inventar que o estudo termina antes do que termina.
 */
export function nextMilestone(pairs: number) {
  return pairs >= PILOT_PAIRS ? TARGET_PAIRS : PILOT_PAIRS;
}

export function milestoneLabel(pairs: number) {
  return pairs >= PILOT_PAIRS ? "confirmatório" : "piloto";
}
