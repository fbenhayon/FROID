export const PERCEPTION_ZONES: Record<number, string> = {
  1:  "Não Reconhecido vs. Autovalidação",
  2:  "Pensamento Repetitivo vs. Pensamento Criativo e Independente",
  3:  "Tristeza vs. Paz Interior",
  4:  "Desconexão Emocional vs. Integração Emocional",
  5:  "Autocrítica vs. Amor Próprio",
  6:  "Amor Condicional vs. Amor Incondicional",
  7:  "Raiva vs. Aceitação da Mudança",
  8:  "Medo e Sobrecarga vs. Responsabilização",
  9:  "Expressão Emocional Suprimida vs. Autoexpressão Adequada",
  10: "Indignidade vs. Autoaceitação",
  11: "Crenças Rígidas vs. Abertura às Possibilidades",
  12: "Crenças e Ações Conflitantes vs. Crenças e Ações Congruentes",
};

export const COLOR_MEANINGS: Record<FroidColor, string> = {
  BRANCO:  "Zonas de compensação contendo menores quantidades de energia vocal (Offsetting)",
  AZUL:    "Zona com baixo nível de desequilíbrio",
  VERDE:   "Zona com nível médio de desequilíbrio",
  AMARELO: "Zona com alto nível de desequilíbrio",
  VERMELHO:"Zona com extremo nível de desequilíbrio",
  PRETO:   "Excesso global de energia em toda a voz",
  CINZA:   "Energia da voz normalizada/distribuída através de todas as zonas",
};

export type FroidColor = "BRANCO" | "AZUL" | "VERDE" | "AMARELO" | "VERMELHO" | "PRETO" | "CINZA";

export interface DissonanceDetails {
  active_aus: string[];
  report: string;
}

export interface PerceptionZone {
  zone: number;
  tema: string;
  deviation_score: number;
  cor_plot: FroidColor;
  facial_dissonance_detected: boolean;
  dissonance_details?: DissonanceDetails;
}

export interface AcousticBiomarkers {
  bioacoustic_window_ms?: number;
  subharmonic_energy_5_12hz?: number;
  subharmonic_energy_12_20hz?: number;
  subharmonic_energy_20_40hz?: number;
  energy_85_165hz?: number;
  spectral_delta_0_4hz?: number;
  spectral_theta_4_8hz?: number;
  spectral_alpha_8_12hz?: number;
  spectral_beta_12_30hz?: number;
  spectral_gamma_30_80hz?: number;
  spectral_band_index?: number;
  dna_infrasound_nuclear?: number;
  dna_limbic_modulation?: number;
  dna_vocal_basal_tension?: number;
  dna_autonomic_flooding?: number;
  dna_dissociative_shutdown?: number;
  dna_neurogenic_resonance?: number;
  dna_somatoaffective_dissonance?: number;
  dna_subharmonic_index?: number;
  dna_baseline_locked?: boolean;
  dna_facial_multiplier?: number;
  clinical_insight?: string | null;
  mfcc7?: number;
  mfcc9?: number;
  baseline_mfcc7?: number;
  baseline_mfcc9?: number;
  desvio_mfcc7?: number;
  desvio_mfcc9?: number;
  mfcc7_delta?: number;
  mfcc9_delta?: number;
  mfcc7_delta_delta?: number;
  mfcc9_delta_delta?: number;
  mfcc9_delta_delta_spastic_threshold?: number;
  mfcc9_delta_delta_spastic_alert?: boolean;
  f0_mean?: number;
  f0_var?: number;
  f0_voiced_ratio?: number;
  f0_source?: string;
  loudness_dbfs?: number;
  voice_features_source?: "real_pcm" | "mock" | string;
  zcr?: number;
  jitter_proxy_index?: number;
  shimmer_proxy_index?: number;
  jitter_unit?: string;
  shimmer_unit?: string;
  jitter_source?: string;
  shimmer_source?: string;
  spectral_band_context?: string;
  jitter?: number;
  shimmer?: number;
  speech_rate?: number;
  loudness?: number;
  spectral_flux?: number;
  pause_duration?: number;
  semantic_valence?: "NEGATIVO" | "NEUTRO" | "POSITIVO" | string;
  substancia_semantica?: "NEGATIVO" | "NEUTRO" | "POSITIVO" | string;
  transcricao_gpt4o?: string;
  alerta_clinico?: string;
  impacto_preditivo?: string;
}

export interface FroidPayload {
  session_id: string;
  timestamp_ms: number;
  ipm_score: number;
  idm_score?: number;
  coherence_status: string;
  global_energy: { cor_plot: FroidColor; descricao: string };
  perception_zones: PerceptionZone[];
  realtime_alerts: string[];
  audio_meta?: AcousticBiomarkers & Record<string, unknown>;
}

export function calculateIDM(vocalEnergy: number, baselineEnergy: number, facialDissonanceFlag: boolean): number {
  const energyDeviationRatio = (vocalEnergy - baselineEnergy) / (baselineEnergy + 1e-9);
  const dissonanceMultiplier = facialDissonanceFlag ? 2.5 : 1.0;
  return energyDeviationRatio * dissonanceMultiplier;
}

export function mapColor(score: number): FroidColor {
  if (score <= -0.5) return "BRANCO";
  if (score <= 0.5) return "AZUL";
  if (score <= 1.5) return "VERDE";
  if (score <= 3.0) return "AMARELO";
  return "VERMELHO";
}

export const HEX_PALETTE: Record<FroidColor, string> = {
  BRANCO:  "#f8fafc",
  AZUL:    "#3b82f6",
  VERDE:   "#22c55e",
  AMARELO: "#eab308",
  VERMELHO:"#ef4444",
  PRETO:   "#0f172a",
  CINZA:   "#6b7280",
};
