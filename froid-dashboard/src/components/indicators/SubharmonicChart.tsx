import React, { useMemo } from "react";
import { AcousticBiomarkers, PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";
import { tooltipText } from "../../lib/tooltip-i18n";
import type { SessionLocale } from "../../lib/localization";

interface Props {
  zones: PerceptionZone[];
  audioMeta?: (AcousticBiomarkers & Record<string, unknown>) | null;
  locale?: SessionLocale;
}

type SubharmonicMetric = {
  id: string;
  label: string;
  band: string;
  value: number;
  color: string;
  source: "acústico" | "proxy";
  // Duas linhas separadas de proposito: `indica` diz o que o marcador
  // mostra, `uso` diz o que o profissional faz com isso. Misturadas num
  // paragrafo so, a leitura vira conclusao sobre a pessoa.
  indica: string;
  uso: string;
};

const DNA_COLORS: Record<string, string> = {
  nuclear_infrasound: "#5CC9FF",
  limbic_12_20: "#6B8CFF",
  vocal_85_165: "#9A5BFF",
  flooding: "#FFB22E",
  shutdown: "#FF5D9B",
  neurogenic: "#66D7FF",
  somatoaffective: "#6EF2A8",
};

const clamp = (value: number, min = 0, max = 1) =>
  Math.min(Math.max(Number.isFinite(value) ? value : 0, min), max);

const percent = (value: number) => Math.round(clamp(value) * 100);

const readNumber = (
  audioMeta: Props["audioMeta"],
  key: keyof AcousticBiomarkers,
) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
};

const readMetaNumber = (
  audioMeta: Props["audioMeta"],
  key: string,
) => {
  const raw = audioMeta?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
};

const readMetric = (
  audioMeta: Props["audioMeta"],
  preferredKey: keyof AcousticBiomarkers,
  fallbackKey?: keyof AcousticBiomarkers,
) => {
  const preferred = readNumber(audioMeta, preferredKey);
  if (preferred !== null) return preferred;
  return fallbackKey ? readNumber(audioMeta, fallbackKey) : null;
};

const zoneLoad = (zones: PerceptionZone[], ids: number[]) => {
  const selected = ids
    .map((id) => zones.find((zone) => zone.zone === id))
    .filter(Boolean) as PerceptionZone[];

  if (!selected.length) return 0;

  const average =
    selected.reduce(
      (sum, zone) => sum + Math.max(0, zone.deviation_score || 0),
      0,
    ) / selected.length;

  return clamp(average / 4);
};

const compensationLoad = (zones: PerceptionZone[]) => {
  const offsets = zones.filter(
    (zone) => zone.cor_plot === "BRANCO" || (zone.deviation_score || 0) < -0.3,
  );
  return clamp(offsets.length / 6);
};

export const SubharmonicChart: React.FC<Props> = ({ zones, audioMeta, locale = "pt-BR" }) => {
  const { metrics, insight, hasAcousticData } = useMemo(() => {
    const arr = Array.isArray(zones)
      ? zones.filter((zone) => zone && typeof zone.zone === "number")
      : [];

    const acoustic5_12 = readMetric(
      audioMeta,
      "dna_infrasound_nuclear",
      "subharmonic_energy_5_12hz",
    );
    const acoustic12_20 = readMetric(
      audioMeta,
      "dna_limbic_modulation",
      "subharmonic_energy_12_20hz",
    );
    const acoustic85_165 = readMetric(
      audioMeta,
      "dna_vocal_basal_tension",
      "energy_85_165hz",
    );
    const acoustic20_40 =
      readMetric(audioMeta, "dna_neurogenic_resonance", "subharmonic_energy_20_40hz") ??
      readMetaNumber(audioMeta, "subharmonic_energy_20_40hz");
    const acousticFlooding = readNumber(audioMeta, "dna_autonomic_flooding");
    const acousticShutdown = readNumber(audioMeta, "dna_dissociative_shutdown");
    const acousticSomato = readNumber(audioMeta, "dna_somatoaffective_dissonance");
    const hasAcoustic =
      acoustic5_12 !== null ||
      acoustic12_20 !== null ||
      acoustic85_165 !== null ||
      acoustic20_40 !== null;

    const dissonanceLoad = clamp(
      arr.filter((zone) => !!zone.facial_dissonance_detected).length / 5,
    );
    const traumaProxy = clamp(zoneLoad(arr, [7, 8, 12]) * 0.72 + dissonanceLoad * 0.28);
    const limbicProxy = clamp(zoneLoad(arr, [2, 8, 11]) * 0.68 + dissonanceLoad * 0.18);
    const tensionProxy = clamp(zoneLoad(arr, [4, 9]) * 0.6 + zoneLoad(arr, [7]) * 0.25);

    const tremor5_12 = acoustic5_12 ?? traumaProxy;
    const upper12_20 = acoustic12_20 ?? limbicProxy;
    const tension85_165 = acoustic85_165 ?? tensionProxy;
    const flooding = acousticFlooding ?? clamp(tremor5_12 * 0.58 + tension85_165 * 0.42);
    const shutdown =
      acousticShutdown ??
      clamp(tremor5_12 * (1 - tension85_165) + compensationLoad(arr) * 0.32);
    const neurogenic = acoustic20_40 ?? clamp(upper12_20 * 0.44 + dissonanceLoad * 0.22);
    const somatoaffective =
      acousticSomato ??
      clamp(tremor5_12 * 0.34 + tension85_165 * 0.34 + dissonanceLoad * 0.32);

    const items: Omit<SubharmonicMetric, "color">[] = [
      {
        id: "nuclear_infrasound",
        label: "Modulação Lenta da Voz",
        band: "5–12 Hz · Comparado à linha de base individual",
        value: tremor5_12,
        source: acoustic5_12 !== null ? "acústico" : "proxy",
        indica: "Oscilação lenta na sustentação vocal.",
        uso:
          "A literatura aponta correlação com mobilização autonômica, mas a medida indica o desvio espectral frente à calibração inicial, cabendo ao clínico validar no contexto.",
      },
      {
        id: "limbic_12_20",
        label: "Modulação Média da Voz",
        band: "12–20 Hz · Transição de envoltória e afeto",
        value: upper12_20,
        source: acoustic12_20 !== null ? "acústico" : "proxy",
        indica: "Variação intermediária na emissão sonora.",
        uso:
          "Auxilia a perceber ressonâncias de reatividade emocional que escapam ao ritmo habitual de fala.",
      },
      {
        id: "vocal_85_165",
        label: "Sustentação da Faixa Grave",
        band: "85–165 Hz · Esforço e tônus laríngeo basal",
        value: tension85_165,
        source: acoustic85_165 !== null ? "acústico" : "proxy",
        indica: "Concentração de energia nos graves da fonação.",
        uso:
          "Sinaliza sobrecarga mecânica ou esforço fonatório associado a retenção de tensão somática.",
      },
      {
        id: "flooding",
        label: "Convergência de Canais (Flooding)",
        band: "5–12 Hz com 85–165 Hz · Elevação síncrona de faixas",
        value: flooding,
        source: hasAcoustic ? "acústico" : "proxy",
        indica: "Ativação simultânea de bandas graves e lentas.",
        uso:
          "Alerta preventivo importante para o terapeuta ponderar o ritmo da sessão e evitar sobrecarga ou retraumatização.",
      },
      {
        id: "shutdown",
        label: "Queda Simultânea de Canais",
        band: "Energia e coerência · Retração de sinal",
        value: shutdown,
        source: hasAcoustic ? "acústico" : "proxy",
        indica: "Redução síncrona de energia expressiva.",
        uso:
          "Pode sinalizar restrição psicomotora, esgotamento ou mecanismos de distanciamento/congelamento defensivo.",
      },
      {
        id: "neurogenic",
        label: "Modulação Rápida da Voz",
        band: "20–40 Hz · Carga sobre a musculatura fina",
        value: neurogenic,
        source: acoustic20_40 !== null ? "acústico" : "proxy",
        indica: "Oscilação rápida na microfonação.",
        uso:
          "Relacionada a microtensão na musculatura laríngea fina, servindo de apoio para notar picos de alerta invisíveis a olho nu.",
      },
      {
        id: "somatoaffective",
        label: "Divergência Somatoafetiva",
        band: "Fala calma com sub-harmônico tenso",
        value: somatoaffective,
        source: "proxy",
        indica: "Quebra de simetria entre o conteúdo verbal e a assinatura acústica.",
        uso:
          "Aponta para o profissional que o paciente relata tranquilidade verbal enquanto o corpo mantém padrões de tensão.",
      },
    ];

    const clinicalInsight =
      typeof audioMeta?.clinical_insight === "string"
        ? audioMeta.clinical_insight
        : tremor5_12 > 0.4 && tension85_165 > 0.6
          ? "ALERTA SEVERO: sobrecarga autonômica crítica por tremor profundo cruzado com tensão vocal."
          : tremor5_12 > 0.4
            ? "ALERTA DE DISSOCIAÇÃO: tremor autonômico profundo predominando sobre a emissão vocal basal."
            : "Sistema Nervoso Autônomo estável. Fluxo simpático regular.";

    return {
      hasAcousticData: hasAcoustic,
      insight: clinicalInsight,
      metrics: items.map((item) => ({
        ...item,
        color: DNA_COLORS[item.id] || "#64748B",
      })),
    };
  }, [zones, audioMeta]);

  const dominant = metrics.reduce(
    (top, metric) => (metric.value > top.value ? metric : top),
    metrics[0],
  );
  const values = metrics.map((metric) => percent(metric.value));
  const maxValue = Math.max(...values, 1);
  const generalIndex = Math.round(
    values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1),
  );

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-sm">
      <div className="mb-1.5 flex shrink-0 items-start justify-between gap-3">
        <FroidTooltip
          width={360}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "Sub-harmônicos vocais")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Componentes de infra-tremor da voz nas faixas de 5 a 165 Hz, usados como pistas de ativação e regulação do Sistema Nervoso Autônomo. É o pilar mais exploratório do FROID — leia como apoio à escuta, nunca como diagnóstico isolado. Quando há sinal acústico real usa-se a medida direta; caso contrário, um proxy derivado das zonas.",
                )}
              </p>
            </div>
          }
        >
          <div className="min-w-0 cursor-help">
            <h3 className="text-[13px] font-black text-slate-100">
              Sub-harmônicos
            </h3>
            <p className="truncate text-[10px] font-medium text-slate-400">
              Percentual por componente e substância técnica
            </p>
          </div>
        </FroidTooltip>
        <FroidTooltip
          width={300}
          content={
            <div>
              <p className="font-bold text-slate-100">{tooltipText(locale, "Índice geral sub-harmônico")}</p>
              <p className="mt-1">
                {tooltipText(
                  locale,
                  "Média dos componentes sub-harmônicos em 0–100%. Resume a carga autonômica global do momento — útil para perceber tendência antes de detalhar cada componente.",
                )}
              </p>
            </div>
          }
        >
          <div className="shrink-0 cursor-help rounded-xl border border-blue-800 bg-blue-950 px-2.5 py-0.5 text-center text-blue-200">
            <span className="block text-[8px] font-black uppercase">
              Índice geral
            </span>
            <strong className="font-mono text-[12px]">{generalIndex}%</strong>
          </div>
        </FroidTooltip>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden pr-1">
        <div className="space-y-2">
          {metrics.map((metric, index) => {
            const value = percent(metric.value);
            return (
              <FroidTooltip
                key={metric.id}
                fullWidth
                content={
                  <div className="max-w-[340px]">
                    <p className="font-bold">
                      {metric.label} ({metric.band})
                    </p>
                    <p className="mt-1 text-[10px] leading-relaxed">
                      <span className="font-bold text-slate-100">O que indica: </span>
                      {tooltipText(locale, metric.indica)}
                    </p>
                    <p className="mt-1 text-[10px] leading-relaxed">
                      <span className="font-bold text-slate-100">Uso clínico: </span>
                      {tooltipText(locale, metric.uso)}
                    </p>
                    <p className="mt-1 text-[9px] leading-relaxed text-slate-400">
                      Procedência: {metric.source}. Leitura clínica é do profissional.
                    </p>
                  </div>
                }
                width={360}
              >
                <div className="w-full cursor-help">
                  <div className="mb-1 grid min-w-0 grid-cols-[12px_minmax(0,1fr)_48px] items-center gap-2">
                    <span
                      className="h-5 w-3 rounded-sm"
                      style={{ backgroundColor: metric.color }}
                    />
                    <div className="min-w-0">
                      <span className="block truncate text-[10px] font-black leading-tight text-slate-100">
                        {index + 1}. {metric.label}
                      </span>
                      <span className="block truncate text-[8px] font-bold leading-tight tracking-wide text-[#9bc9ff]">
                        {metric.band}
                      </span>
                    </div>
                    <span className="text-right font-mono text-[10px] font-black text-slate-100">
                      {value}%
                    </span>
                  </div>
                  <div className="ml-5 h-2.5 w-[calc(100%-1.25rem)] overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${(value / maxValue) * 100}%`,
                        backgroundColor: metric.color,
                      }}
                    />
                  </div>
                </div>
              </FroidTooltip>
            );
          })}
        </div>
      </div>

      <p className="mt-1 shrink-0 truncate text-[8px] font-medium text-slate-400">
        {dominant.label}: {percent(dominant.value)}% |{" "}
        {hasAcousticData ? "acústico" : "proxy"} | {insight}
      </p>
    </div>
  );
};
