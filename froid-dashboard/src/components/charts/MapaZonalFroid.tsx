import React, { useMemo, useState } from "react";
import { tooltipText } from "../../lib/tooltip-i18n";
import type { SessionLocale } from "../../lib/localization";

type ZoneInput = {
  zone?: number;
  zona?: number;
  id?: number;
  deviation_score?: number | null;
  idm?: number | null;
  score?: number | null;
};

type NormalizedZone = {
  zone: number;
  deviation_score: number;
  hasData: boolean;
};

type MapaZonalFroidProps = {
  zones?: ZoneInput[] | null;
  baselineIpm?: number | null;
  drValue?: number | null;
  isCalibrating?: boolean;
  className?: string;
  locale?: SessionLocale;
};

const NEGATIVES = [
  "Desvalorizado",
  "Pensamento Repetitivo",
  "Tristeza",
  "Desconexão Emocional",
  "Autocrítica",
  "Amor Condicional",
  "Raiva",
  "Medo e Sobrecarga",
  "Emoção Suprimida",
  "Indignidade",
  "Crenças Rígidas",
  "Crenças/Ações Conflitantes",
];

const POSITIVES = [
  "Autovalidação",
  "Pensamento Criativo",
  "Paz Interior",
  "Integração Emocional",
  "Amor Próprio",
  "Amor Incondicional",
  "Aceitação da Mudança",
  "Responsabilização",
  "Expressão Adequada",
  "Autoaceitação",
  "Cognitivo",
  "Crenças/Ações Congruentes",
];

const NEGATIVE_COLORS = ["#F7B7B7", "#E85D5D", "#B91C1C"];
const POSITIVE_COLORS = ["#BFE7FF", "#5B8DEF", "#22C55E"];
const NEUTRAL_COLOR = "#CBD5E1";
const IDM_HELP =
  "O Índice de Desvio Multimodal (IDM) é uma métrica central na arquitetura diagnóstica do sistema FROID, projetada para medir a direção e o grau de desequilíbrio da energia de um paciente nas 12 zonas específicas de percepção psíquica. Maiores detalhes Pergunte ao FROID.";

const ZONE_DESCRIPTIONS = [
  "Zona 1 — Reconhecimento. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a reconhecimento e validacao. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 2 — Ruminacao. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a circuitos repetitivos de pensamento e fadiga mental. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 3 — Ancoragem no passado. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a conteudo verbal ancorado em eventos passados. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 4 — Distanciamento afetivo. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a distanciamento entre relato e expressao afetiva. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 5 — Autocritica. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a foco verbal em falhas e defeitos proprios. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 6 — Vinculo condicional. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a exigencia e controle na descricao de vinculos. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 7 — Raiva defensiva. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a irritacao sustentada com tensao muscular captavel. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 8 — Passividade. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a posicao passiva diante dos proprios eventos. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 9 — Negacao de sentimentos. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a supressao verbal do que a expressao sinaliza. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 10 — Merecimento. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a desqualificacao do proprio merecimento. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 11 — Rigidez cognitiva. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a regras absolutas e baixa tolerancia a ambiguidade. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
  "Zona 12 — Incongruencia desejo-crenca. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a divergencia entre o desejo declarado e a crenca expressa. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.",
];

function clamp(value: number, min = 0, max = 1) {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

function hexToRgb(hex: string) {
  const clean = hex.replace("#", "");
  return {
    r: parseInt(clean.slice(0, 2), 16),
    g: parseInt(clean.slice(2, 4), 16),
    b: parseInt(clean.slice(4, 6), 16),
  };
}

function rgbToHex(r: number, g: number, b: number) {
  const toHex = (v: number) =>
    Math.round(clamp(v, 0, 255))
      .toString(16)
      .padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function interpolateColor(colors: string[], t: number) {
  const val = clamp(t, 0, 1);
  const seg = val <= 0.5 ? 0 : 1;
  const localT = seg === 0 ? val / 0.5 : (val - 0.5) / 0.5;
  const s = hexToRgb(colors[seg]);
  const e = hexToRgb(colors[seg + 1]);
  return rgbToHex(
    s.r + (e.r - s.r) * localT,
    s.g + (e.g - s.g) * localT,
    s.b + (e.b - s.b) * localT,
  );
}

function getZoneNumber(item: ZoneInput) {
  const raw = item.zone ?? item.zona ?? item.id;
  if (typeof raw !== "number" || !Number.isFinite(raw)) return null;
  const z = Math.round(raw);
  return z < 1 || z > 12 ? null : z;
}

function getDeviationScore(item: ZoneInput) {
  const raw = item.deviation_score ?? item.idm ?? item.score ?? 0;
  return typeof raw !== "number" || !Number.isFinite(raw) ? 0 : raw;
}

function formatScore(value: number) {
  if (!Number.isFinite(value) || Math.abs(value) < 0.005) return "+0.00";
  return value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
}

export default function MapaZonalFroid({
  zones = [],
  baselineIpm = null,
  drValue = null,
  isCalibrating = false,
  className = "",
  locale = "pt-BR",
}: MapaZonalFroidProps) {
  const [hoveredZone, setHoveredZone] = useState<number | null>(null);
  const [showIdmHelp, setShowIdmHelp] = useState(false);

  const normalizedZones = useMemo<NormalizedZone[]>(() => {
    const base: NormalizedZone[] = Array.from({ length: 12 }, (_, i) => ({
      zone: i + 1,
      deviation_score: 0,
      hasData: false,
    }));

    if (!Array.isArray(zones)) return base;

    zones.forEach((item) => {
      if (!item || typeof item !== "object") return;
      const zn = getZoneNumber(item);
      if (!zn) return;

      base[zn - 1] = {
        zone: zn,
        deviation_score: getDeviationScore(item),
        hasData: true,
      };
    });

    return base;
  }, [zones]);

  const maxAbs = useMemo(
    () =>
      Math.max(
        ...normalizedZones.map((item) => Math.abs(item.deviation_score)),
        0.01,
      ),
    [normalizedZones],
  );

  const baselineLabel = isCalibrating
    ? "CALIB..."
    : typeof baselineIpm === "number" && Number.isFinite(baselineIpm)
      ? baselineIpm.toFixed(1)
      : "--";

  const drLabel =
    typeof drValue === "number" && Number.isFinite(drValue)
      ? drValue.toFixed(2)
      : "--";

  return (
    <div
      className={[
        "flex h-full w-full flex-col overflow-visible rounded-xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-sm",
        className,
      ].join(" ")}
    >
      <div className="mb-1 grid grid-cols-[24px_minmax(96px,0.9fr)_minmax(220px,1.8fr)_minmax(96px,0.9fr)] items-center gap-x-1">
        <div className="text-[10px] font-semibold uppercase tracking-tight text-slate-400">
          Z
        </div>
        <div className="text-right text-[10px] font-black uppercase tracking-tight text-red-400">
          Negativo
        </div>
        <div className="relative flex items-center justify-center gap-2 text-[11px] font-black uppercase tracking-tight text-cyan-300">
          <span>DR: {drLabel}</span>
          <span className="text-slate-600">|</span>
          <span>Base: {baselineLabel}</span>
          <button
            type="button"
            className="rounded-full border border-cyan-700 bg-slate-900 px-1.5 py-0.5 text-[10px] font-bold text-cyan-200 hover:bg-slate-800"
            onClick={() => setShowIdmHelp((current) => !current)}
            onMouseEnter={() => setShowIdmHelp(true)}
            onMouseLeave={() => setShowIdmHelp(false)}
          >
            IDM
          </button>
          {showIdmHelp && (
            <div className="absolute left-1/2 top-full z-50 mt-1 w-80 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-2 text-[10px] normal-case tracking-normal text-slate-600 shadow-2xl">
              <p className="font-bold uppercase tracking-tight text-slate-900">
                IDM
              </p>
              <p className="mt-1 leading-tight">{tooltipText(locale, IDM_HELP)}</p>
            </div>
          )}
        </div>
        <div className="text-left text-[10px] font-black uppercase tracking-tight text-green-400">
          Positivo
        </div>
      </div>

      <div className="grid flex-1 auto-rows-fr grid-cols-[24px_minmax(96px,0.9fr)_minmax(220px,1.8fr)_minmax(96px,0.9fr)] gap-x-1">
        {normalizedZones.map((item, index) => {
          const zn = item.zone;
          const val = item.deviation_score;
          const isNeg = val < -0.005;
          const isPos = val > 0.005;
          const isNeu = !isNeg && !isPos;
          const intensity = item.hasData
            ? clamp(Math.abs(val) / maxAbs, 0, 1)
            : 0;
          const barW = intensity * 42;
          const color = isNeu
            ? NEUTRAL_COLOR
            : isNeg
              ? interpolateColor(NEGATIVE_COLORS, intensity)
              : interpolateColor(POSITIVE_COLORS, intensity);
          const tooltipUp = zn >= 9;
          const zoneLabel = isNeg
            ? NEGATIVES[index]
            : isPos
              ? POSITIVES[index]
              : "Neutro";

          return (
            <React.Fragment key={zn}>
              <div
                className="flex h-full min-h-0 items-center justify-end pr-0.5 text-[10px] font-bold text-slate-300"
                onMouseEnter={() => setHoveredZone(zn)}
                onMouseLeave={() => setHoveredZone(null)}
              >
                {zn}.
              </div>

              <div
                className="flex h-full min-h-0 items-center justify-end truncate pr-0.5 text-right text-[10px] font-semibold leading-none text-slate-300"
                onMouseEnter={() => setHoveredZone(zn)}
                onMouseLeave={() => setHoveredZone(null)}
              >
                {NEGATIVES[index]}
              </div>

              <div
                className="relative flex h-full min-h-0 items-center overflow-visible"
                onMouseEnter={() => setHoveredZone(zn)}
                onMouseLeave={() => setHoveredZone(null)}
              >
                <div className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-slate-800" />
                <div className="absolute left-1/2 top-0 z-10 h-full w-px border-l border-dashed border-cyan-300" />

                {isNeg && (
                  <div
                    className="absolute right-1/2 top-1/2 h-2.5 -translate-y-1/2 rounded-l-full transition-all duration-700"
                    style={{ width: `${barW}%`, backgroundColor: color }}
                  />
                )}
                {isPos && (
                  <div
                    className="absolute left-1/2 top-1/2 h-2.5 -translate-y-1/2 rounded-r-full transition-all duration-700"
                    style={{ width: `${barW}%`, backgroundColor: color }}
                  />
                )}
                {isNeu && (
                  <div className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-slate-300" />
                )}

                {!isNeu && (
                  <div
                    className={`absolute top-1/2 -translate-y-1/2 text-[9px] font-bold text-slate-100 transition-all duration-700 ${
                      isNeg
                        ? "right-[calc(50%+var(--bw)+4px)]"
                        : "left-[calc(50%+var(--bw)+4px)]"
                    }`}
                    style={{ "--bw": `${barW}%` } as React.CSSProperties}
                  >
                    {formatScore(val)}
                  </div>
                )}

                {hoveredZone === zn && (
                  <div
                    className={`absolute left-1/2 z-50 w-80 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-2 text-[10px] shadow-2xl ${
                      tooltipUp ? "bottom-full mb-1" : "top-full mt-1"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-bold text-slate-900">Zona {zn}</p>
                      <span
                        className={`rounded px-1 py-0.5 text-[8px] font-bold ${
                          isNeg
                            ? "bg-red-100 text-red-700"
                            : isPos
                              ? "bg-green-100 text-green-700"
                              : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        IDM {formatScore(val)}
                      </span>
                    </div>
                    <p className="mt-1 text-[9px] leading-tight text-slate-600">
                      {zoneLabel}
                    </p>
                    <p className="mt-1 border-t border-slate-100 pt-1 text-[9px] leading-tight text-slate-600">
                      {tooltipText(locale, ZONE_DESCRIPTIONS[index])}
                    </p>
                  </div>
                )}
              </div>

              <div
                className="flex h-full min-h-0 items-center justify-start truncate pl-0.5 text-left text-[10px] font-semibold leading-none text-slate-300"
                onMouseEnter={() => setHoveredZone(zn)}
                onMouseLeave={() => setHoveredZone(null)}
              >
                {POSITIVES[index]}
              </div>
            </React.Fragment>
          );
        })}
      </div>

      <div className="mt-1 flex flex-wrap justify-center gap-2 border-t border-slate-100 pt-1 text-[8px] text-slate-500">
        <div className="flex items-center gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: NEGATIVE_COLORS[0] }}
          />
          Neg
        </div>
        <div className="flex items-center gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: NEGATIVE_COLORS[2] }}
          />
          Alt
        </div>
        <div className="flex items-center gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: POSITIVE_COLORS[0] }}
          />
          Pos
        </div>
        <div className="flex items-center gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: POSITIVE_COLORS[2] }}
          />
          Alt
        </div>
      </div>
    </div>
  );
}
