import React, { useMemo, useState } from "react";

type ZoneInput = { zone?: number; zona?: number; id?: number; deviation_score?: number | null; idm?: number | null; score?: number | null; };
type NormalizedZone = { zone: number; deviation_score: number; hasData: boolean; };
type MapaZonalFroidProps = { zones?: ZoneInput[] | null; baselineIpm?: number | null; isCalibrating?: boolean; className?: string; };

// Listas de Rótulos
const NEGATIVES = ["Não Reconhecido", "Pensamento Repetitivo", "Tristeza", "Desconexão Emocional", "Autocrítica", "Amor Condicional", "Raiva", "Medo e Sobrecarga", "Expressão Emocional Suprimida", "Indignidade", "Crenças Rígidas", "Crenças e Ações Conflitantes"];
const POSITIVES = ["Autovalidação", "Pensamento Criativo e Independente", "Paz Interior", "Integração Emocional", "Amor Próprio", "Amor Incondicional", "Aceitação da Mudança", "Responsabilização", "Autoexpressão Adequada", "Autoaceitação", "Abertura às Possibilidades", "Crenças e Ações Congruentes"];

// Descrições Clínicas Completas (Conforme Solicitado)
const FULL_DESCRIPTIONS = [
  "Quando o FROID aponta sobrecarga na Zona 1, o paciente apresenta a percepção de não ser reconhecido, manifestando-se por meio de padrões de negação, evasão e desconfiança. A desvalorização frequentemente surge disfarçada ou através da baixa autoestima. <br/><br/><strong>Diretriz Clínica:</strong> Estimular a transição para a autovalidação, ajudando o paciente a confiar na própria percepção como base segura.",
  "Acionada quando o paciente fica aprisionado em circuitos lógicos e repetitivos que não conseguem filtrar pensamentos improdutivos. O FROID rastreia esse estresse subconsciente, muitas vezes ligado a medos ou dúvidas. <br/><br/><strong>Diretriz Clínica:</strong> Abordar a fadiga mental (precursora da depressão) e guiar o cérebro à liberação deste padrão, restaurando a criatividade autêntica.",
  "O motor do FROID detecta pensamentos excessivamente ancorados em eventos passados, rotulados como fracassos e perdas. A IA denuncia baixos níveis de energia global na voz. <br/><br/><strong>Diretriz Clínica:</strong> Visar o desligamento de experiências traumáticas. A paz interior é alcançada guiando o indivíduo para a autoaceitação e permanência no presente.",
  "O FROID flagra essa zona quando o paciente parece excessivamente racional, distante, ou relata dificuldade em acessar sentimentos. Pode haver tensão em pescoço/garganta decorrente do medo de rejeição. <br/><br/><strong>Diretriz Clínica:</strong> Reverter o embotamento. A integração demonstrará a restauração da consciência emocional, permitindo vivenciar sentimentos com profundidade.",
  "O sistema capta tensões geradas pela falta de compaixão consigo mesmo, revelando foco excessivo em defeitos e falhas, geralmente desencadeado por experiências de rejeição. <br/><br/><strong>Diretriz Clínica:</strong> Romper o ciclo de não-se-sentir-amado, construindo perdão e autoamor. Sucesso é reconhecer valor independente de aprovações externas.",
  "O FROID alerta para padrões onde o paciente baseia vínculos em julgamentos, expectativas rígidas e controle. Essa zona esconde fortes sentimentos de insuficiência e insegurança. <br/><br/><strong>Diretriz Clínica:</strong> Trabalhar a desconstrução das exigências transacionais, movendo a psique em direção à tolerância e ao amor incondicional.",
  "O monitoramento indicará a raiva como mecanismo de defesa para encobrir sofrimento, traição ou perda. Quando crônica, causa intensa tensão muscular captável no rosto e na voz. <br/><br/><strong>Diretriz Clínica:</strong> Alcançar a aceitação da mudança para cessar a reação defensiva perpétua e permitir adaptações saudáveis.",
  "Sinalizada quando o indivíduo exibe acústica de vitimização, sentindo que a vida 'lhe acontece'. O medo estará enraizado em críticas severas ou punições passadas. <br/><br/><strong>Diretriz Clínica:</strong> Guiar a transição da paralisia passiva para o empoderamento e responsabilização, desenvolvendo autonomia.",
  "Uma das dissonâncias mais rastreáveis. Ocorre quando sentimentos são negados repetidamente, criando dificuldade de comunicação ou timidez excessiva. Sintomas físicos podem aparecer na mandíbula. <br/><br/><strong>Diretriz Clínica:</strong> Estimular a comunicação de sentimentos e necessidades de forma clara e respeitosa, fortalecendo a autoestima.",
  "O sistema revelará a 'Síndrome do Impostor': a conclusão inconsciente de que não se merece amor ou sucesso. Gera autossabotagem e desconforto diante de conquistas. <br/><br/><strong>Diretriz Clínica:</strong> Ensinar a aceitação de virtudes e limitações sem cobrança por perfeição. A autoaceitação forma a base para relações saudáveis.",
  "O FROID mapeará a inflexibilidade cognitiva. O paciente formula regras mentais absolutas para se proteger da incerteza, restringindo adaptações e criatividade. <br/><br/><strong>Diretriz Clínica:</strong> Atuar na dissolução dogmática, conduzindo à tolerância à ambiguidade, curiosidade e perspectivas inovadoras.",
  "O núcleo da detecção. Ocorre incompatibilidade entre o desejo consciente e a crença subconsciente limitante. Gera indecisão, fadiga mental massiva e estagnação sistêmica. <br/><br/><strong>Diretriz Clínica:</strong> Focar no alinhamento psíquico absoluto. Criar congruência interna onde pensamento, crença, emoção e ação convirjam para a mesma direção."
];

const NEGATIVE_COLORS = ["#F7B7B7", "#E85D5D", "#B91C1C"];
const POSITIVE_COLORS = ["#BFE7FF", "#5B8DEF", "#22C55E"];
const NEUTRAL_COLOR = "#CBD5E1";

function clamp(value: number, min = 0, max = 1) { if (!Number.isFinite(value)) return min; return Math.min(Math.max(value, min), max); }
function hexToRgb(hex: string) { const clean = hex.replace("#", ""); return { r: parseInt(clean.slice(0, 2), 16), g: parseInt(clean.slice(2, 4), 16), b: parseInt(clean.slice(4, 6), 16) }; }
function rgbToHex(r: number, g: number, b: number) { const toHex = (v: number) => Math.round(clamp(v, 0, 255)).toString(16).padStart(2, "0"); return `#${toHex(r)}${toHex(g)}${toHex(b)}`; }
function interpolateColor(colors: string[], t: number) { const val = clamp(t, 0, 1); const seg = val <= 0.5 ? 0 : 1; const localT = seg === 0 ? val / 0.5 : (val - 0.5) / 0.5; const s = hexToRgb(colors[seg]); const e = hexToRgb(colors[seg + 1]); return rgbToHex(s.r + (e.r - s.r) * localT, s.g + (e.g - s.g) * localT, s.b + (e.b - s.b) * localT); }
function getZoneNumber(item: ZoneInput) { const raw = item.zone ?? item.zona ?? item.id; if (typeof raw !== "number" || !Number.isFinite(raw)) return null; const z = Math.round(raw); return (z < 1 || z > 12) ? null : z; }
function getDeviationScore(item: ZoneInput) { const raw = item.deviation_score ?? item.idm ?? item.score ?? 0; return (typeof raw !== "number" || !Number.isFinite(raw)) ? 0 : raw; }
function formatScore(value: number) { if (!Number.isFinite(value) || Math.abs(value) < 0.005) return "+0.00"; return value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2); }

export default function MapaZonalFroid({ zones = [], baselineIpm = null, isCalibrating = false, className = "" }: MapaZonalFroidProps) {
  const [hoveredZone, setHoveredZone] = useState<number | null>(null);
  const [showIdmHelp, setShowIdmHelp] = useState(false);

  const normalizedZones = useMemo<NormalizedZone[]>(() => {
    const base: NormalizedZone[] = Array.from({ length: 12 }, (_, i) => ({ zone: i + 1, deviation_score: 0, hasData: false }));
    if (!Array.isArray(zones)) return base;
    zones.forEach((item) => {
      if (!item || typeof item !== "object") return;
      const zn = getZoneNumber(item);
      if (!zn) return;
      base[zn - 1] = { zone: zn, deviation_score: getDeviationScore(item), hasData: true };
    });
    return base;
  }, [zones]);

  const maxAbs = useMemo(() => Math.max(...normalizedZones.map(i => Math.abs(i.deviation_score)), 0.01), [normalizedZones]);
  const centerLabel = isCalibrating ? "CALIB..." : (typeof baselineIpm === "number" && Number.isFinite(baselineIpm)) ? `${baselineIpm.toFixed(1)} IPM` : "DR";

  return (
    <div className={["w-full overflow-visible rounded-2xl border border-slate-200 bg-white p-5 shadow-sm", className].join(" ")}>
      {/* Header */}
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-bold tracking-wide text-slate-900">MAPA ZONAL DE PERCEPÇÃO FROID</h2>
          <p className="mt-1 text-xs text-slate-500">Índice de Desvio Multimodal — negativos à esquerda, positivos à direita</p>
        </div>
        <div className="relative">
          <button type="button" onClick={() => setShowIdmHelp(c => !c)} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-100">O que é IDM?</button>
          {showIdmHelp && (
            <div className="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-600 shadow-xl">
              <p className="font-bold text-slate-900">IDM — Índice de Desvio Multimodal</p>
              <p className="mt-2 leading-relaxed">Funciona como uma bússola clínica. Valores negativos apontam para bloqueio/conflito; positivos para integração/autorregulação.</p>
            </div>
          )}
        </div>
      </div>

      {/* Colunas Header: NEGATIVOS | IDM | POSITIVOS */}
      <div className="grid grid-cols-[44px_minmax(180px,1.4fr)_minmax(300px,2fr)_minmax(180px,1.4fr)] gap-x-3 mb-2">
        <div />
        <div className="border-b-2 border-red-100 pb-2 text-left text-xs font-black text-red-700 uppercase tracking-wider">Negativos</div>
        <div className="relative border-b-2 border-slate-200 pb-2 text-center">
          <span className="text-xs font-black text-slate-800 uppercase tracking-wider">IDM (Base)</span>
          <div className="mt-1 text-[10px] font-mono font-bold text-blue-600 bg-blue-50 inline-block px-2 py-0.5 rounded">{centerLabel}</div>
        </div>
        <div className="border-b-2 border-green-100 pb-2 text-right text-xs font-black text-green-700 uppercase tracking-wider">Positivos</div>
      </div>

      {/* Linhas das Zonas */}
      <div className="grid grid-cols-[44px_minmax(180px,1.4fr)_minmax(300px,2fr)_minmax(180px,1.4fr)] gap-x-3">
        {normalizedZones.map((item, index) => {
          const zn = index + 1;
          const val = item.deviation_score;
          const isNeg = val < -0.005;
          const isPos = val > 0.005;
          const isNeu = !isNeg && !isPos;
          const intensity = item.hasData ? clamp(Math.abs(val) / maxAbs, 0, 1) : 0;
          const barW = intensity * 50; // 50% max width
          const color = isNeu ? NEUTRAL_COLOR : (isNeg ? interpolateColor(NEGATIVE_COLORS, intensity) : interpolateColor(POSITIVE_COLORS, intensity));
          const tooltipUp = zn >= 9;

          return (
            <React.Fragment key={zn}>
              {/* Coluna 1: Número */}
              <div className="flex h-14 items-center justify-end pr-2 text-xs font-bold text-slate-700" onMouseEnter={() => setHoveredZone(zn)} onMouseLeave={() => setHoveredZone(null)}>{zn}.</div>
              
              {/* Coluna 2: Label Negativo */}
              <div className="flex h-14 items-center justify-end text-right pr-3 text-xs font-semibold text-slate-600 leading-tight" onMouseEnter={() => setHoveredZone(zn)} onMouseLeave={() => setHoveredZone(null)}>{NEGATIVES[index]}</div>
              
              {/* Coluna 3: Gráfico Central */}
              <div className="relative flex h-14 items-center overflow-visible" onMouseEnter={() => setHoveredZone(zn)} onMouseLeave={() => setHoveredZone(null)}>
                <div className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-slate-100" />
                <div className="absolute left-1/2 top-0 z-10 h-full w-px border-l border-dashed border-slate-400" />

                {isNeg && <div className="absolute right-1/2 top-1/2 h-3 -translate-y-1/2 rounded-l-full transition-all duration-700" style={{ width: `${barW}%`, backgroundColor: color }} />}
                {isPos && <div className="absolute left-1/2 top-1/2 h-3 -translate-y-1/2 rounded-r-full transition-all duration-700" style={{ width: `${barW}%`, backgroundColor: color }} />}
                {isNeu && <div className="absolute left-1/2 top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-slate-300" />}

                {!isNeu && (
                  <div className={`absolute top-1/2 -translate-y-1/2 text-xs font-bold text-slate-800 transition-all duration-700 ${isNeg ? 'right-[calc(50%+var(--bw)+8px)]' : 'left-[calc(50%+var(--bw)+8px)]'}`} style={{ '--bw': `${barW}%` } as any}>
                    {formatScore(val)}
                  </div>
                )}

                {/* Tooltip */}
                {hoveredZone === zn && (
                  <div className={`absolute left-1/2 z-50 w-96 -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-4 text-xs shadow-2xl ${tooltipUp ? 'bottom-full mb-3' : 'top-full mt-3'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-bold text-slate-900 text-sm">Zona {zn}: {isNeg ? `${NEGATIVES[index]} vs. ${POSITIVES[index]}` : isPos ? `${POSITIVES[index]} vs. ${NEGATIVES[index]}` : `${NEGATIVES[index]} ↔ ${POSITIVES[index]}`}</p>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${isNeg ? 'bg-red-100 text-red-700' : isPos ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                        IDM: {formatScore(val)}
                      </span>
                    </div>
                    <div className="text-slate-600 leading-relaxed space-y-2" dangerouslySetInnerHTML={{ __html: FULL_DESCRIPTIONS[index] }} />
                  </div>
                )}
              </div>

              {/* Coluna 4: Label Positivo */}
              <div className="flex h-14 items-center justify-start text-left pl-3 text-xs font-semibold text-slate-600 leading-tight" onMouseEnter={() => setHoveredZone(zn)} onMouseLeave={() => setHoveredZone(null)}>{POSITIVES[index]}</div>
            </React.Fragment>
          );
        })}
      </div>

      {/* Legenda */}
      <div className="mt-6 flex flex-wrap justify-center gap-6 text-[11px] text-slate-500 border-t border-slate-100 pt-4">
        <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ backgroundColor: NEGATIVE_COLORS[0] }} />Negativo baixo</div>
        <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ backgroundColor: NEGATIVE_COLORS[2] }} />Negativo alto</div>
        <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ backgroundColor: POSITIVE_COLORS[0] }} />Positivo baixo</div>
        <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ backgroundColor: POSITIVE_COLORS[2] }} />Positivo alto</div>
      </div>
    </div>
  );
}
