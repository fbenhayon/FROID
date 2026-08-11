import type { EvidentMarker } from "./froid-engine";

/**
 * Junta a lista completa de métricas com os limites que o servidor calcula.
 *
 * As duas informações existiam separadas: o layout Simplificado mostrava TODAS
 * as métricas em faixa rolante, sem cor nenhuma; o layout Índices mostrava só
 * os marcadores COM métrica base, esses sim coloridos. Quem quisesse o conjunto
 * completo com a indicação de quem saiu da faixa precisava alternar entre os
 * dois e comparar de cabeça.
 *
 * Aqui as duas se encontram. O servidor já entrega `band: [min, max]` e
 * `direction`, então nada é recalculado no navegador — só correlacionado.
 *
 * A distinção entre ACIMA e ABAIXO importa e não estava sendo feita: o painel
 * pintava tudo de vermelho quando `breached`. Uma métrica que caiu abaixo do
 * piso e outra que estourou o teto pedem leituras opostas, e a cor é a primeira
 * coisa que o profissional vê.
 */

export type MetricStatus = "acima" | "abaixo" | "dentro" | "sem-limite";

export type BoundedMetric = {
  label: string;
  value: string;
  status: MetricStatus;
  /** Faixa declarada pelo servidor, quando existe. Para o tooltip. */
  band?: [number | null, number | null];
  /** Leitura do motor, quando existe. */
  interpretation?: string;
};

/**
 * De-para entre o rótulo da tabela e a chave do marcador do servidor.
 *
 * Escrevi antes que normalizar acento, caixa e separador dispensaria esta
 * tabela. Estava errado, e o teste mostrou: "SUB-H" não vira "subharmonic" por
 * normalização nenhuma, e o servidor nomeia por FENÔMENO — "ipm_hyper",
 * "zcr_dev", "mfcc7_spastic" — enquanto a tabela nomeia por GRANDEZA. Medido,
 * a normalização sozinha casava 3 dos 14 marcadores.
 *
 * A tabela de fato envelhece: marcador novo no servidor não aparece aqui e a
 * métrica sai como "sem-limite". Isso é degradação segura — a métrica continua
 * visível, apenas sem régua — e é preferível a inventar correspondência por
 * semelhança de texto, que erraria em silêncio e pintaria a métrica errada.
 */
const ALIASES: Record<string, string> = {
  IPM: "ipm_hyper",
  ZONAS: "zone_extreme",
  "DISSO.": "facial_contradiction",
  ZCR: "zcr_dev",
  "F0 MED.": "f0_baseline_dev",
  DDMFCC7: "mfcc7_spastic",
  DDMFCC9: "mfcc9_spastic",
  "DNA FLOOD": "dna_flooding",
  "DNA SHUTDOWN": "dna_shutdown",
};

/** Normaliza para comparar sem acento, sem separador e sem caixa. Resolve os
 *  casos em que rótulo e chave só diferem por formatação — jitter, shimmer. */
export function normalizeKey(text: string): string {
  return String(text || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function statusFrom(marker: EvidentMarker): MetricStatus {
  const direcao = String(marker.direction || "").toLowerCase();
  if (direcao === "acima" || direcao === "abaixo") return direcao;
  // `breached` sem direção declarada ainda é ruptura: melhor sinalizar sem
  // dizer o lado do que engolir a informação.
  if (marker.breached) return "acima";
  return "dentro";
}

/**
 * Correlaciona as métricas exibidas com os marcadores do servidor.
 *
 * Métrica sem marcador correspondente sai como "sem-limite" — declaradamente
 * sem faixa avaliável, e não pintada como se estivesse dentro. Fingir que uma
 * métrica está normal quando ninguém a avaliou é pior do que dizer que não há
 * régua para ela.
 */
export function withBounds(
  entries: Array<[string, string]>,
  markers: EvidentMarker[],
): BoundedMetric[] {
  const porChave = new Map<string, EvidentMarker>();
  for (const marker of markers || []) {
    for (const candidato of [marker.key, marker.label]) {
      const chave = normalizeKey(candidato);
      if (chave && !porChave.has(chave)) porChave.set(chave, marker);
    }
  }

  return (entries || []).map(([label, value]) => {
    // O alias tem precedência: ele nomeia o fenômeno que o servidor mede, e a
    // normalização é só o atalho para os casos em que os dois já coincidem.
    const alias = ALIASES[label];
    const marker =
      (alias ? porChave.get(normalizeKey(alias)) : undefined)
      || porChave.get(normalizeKey(label));
    if (!marker) return { label, value, status: "sem-limite" as MetricStatus };
    return {
      label,
      value,
      status: statusFrom(marker),
      band: marker.band,
      interpretation: marker.interpretation,
    };
  });
}

/** Classes de cor por situação. Fora da faixa não é tudo igual: acima e abaixo
 *  pedem leituras opostas, e o profissional vê a cor antes do número. */
export const STATUS_CLASSES: Record<MetricStatus, { box: string; label: string; value: string }> = {
  acima: {
    box: "border-red-600 bg-red-950/60",
    label: "text-red-200",
    value: "text-red-100",
  },
  abaixo: {
    box: "border-amber-600 bg-amber-950/50",
    label: "text-amber-200",
    value: "text-amber-100",
  },
  dentro: {
    box: "border-slate-800 bg-slate-900",
    label: "text-slate-400",
    value: "text-cyan-200",
  },
  "sem-limite": {
    box: "border-slate-800 bg-slate-900/60",
    label: "text-slate-500",
    value: "text-slate-300",
  },
};

export function statusLabel(status: MetricStatus): string {
  return {
    acima: "acima do limite — reavaliar",
    abaixo: "abaixo do limite — reavaliar",
    dentro: "dentro da faixa",
    "sem-limite": "sem faixa avaliável nesta leitura",
  }[status];
}

/** Quantas saíram da faixa. Alimenta o contador do cabeçalho, para o
 *  profissional saber que há o que olhar sem varrer a grade inteira. */
export function countOutOfBounds(metrics: BoundedMetric[]): number {
  return metrics.filter((m) => m.status === "acima" || m.status === "abaixo").length;
}
