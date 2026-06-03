import React, { useMemo } from "react";
import { PerceptionZone } from "../../lib/froid-engine";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  zones: PerceptionZone[];
  baselineIPM?: number | null;
  baselineEstablished?: boolean;
}

// --- TRADUÇÃO LITERAL DO PYTHON ---

// Dados Fixos (Python: negativos / positivos)
const NEGATIVES = [
  "Não Reconhecido", "Pensamento Repetitivo", "Tristeza", "Desconexão Emocional",
  "Autocrítica", "Amor Condicional", "Raiva", "Medo e Sobrecarga",
  "Expressão Emocional Suprimida", "Indignidade", "Crenças Rígidas", "Crenças e Ações Conflitantes"
];

const POSITIVES = [
  "Autovalidação", "Pensamento Criativo", "Paz Interior", "Integração Emocional",
  "Amor Próprio", "Amor Incondicional", "Aceitação da Mudança", "Responsabilização",
  "Autoexpressão Adequada", "Autoaceitação", "Abertura às Possibilidades", "Ações Congruentes"
];

// Cores Python (Hex codes extraídos do LinearSegmentedColormap)
// Negativo: #F7B7B7 -> #E85D5D -> #B91C1C
// Positivo: #BFE7FF -> #5B8DEF -> #22C55E
const interpolate = (c1: string, c2: string, f: number) => {
  const r1 = parseInt(c1.slice(1,3), 16), g1 = parseInt(c1.slice(3,5), 16), b1 = parseInt(c1.slice(5,7), 16);
  const r2 = parseInt(c2.slice(1,3), 16), g2 = parseInt(c2.slice(3,5), 16), b2 = parseInt(c2.slice(5,7), 16);
  return `#${Math.round(r1+f*(r2-r1)).toString(16).padStart(2,'0')}${Math.round(g1+f*(g2-g1)).toString(16).padStart(2,'0')}${Math.round(b1+f*(b2-b1)).toString(16).padStart(2,'0')}`;
};

const getNegColor = (v: number, max: number) => {
  const t = Math.min(Math.abs(v)/max, 1);
  if (t < 0.5) return interpolate("#F7B7B7", "#E85D5D", t*2);
  return interpolate("#E85D5D", "#B91C1C", (t-0.5)*2);
};

const getPosColor = (v: number, max: number) => {
  const t = Math.min(Math.abs(v)/max, 1);
  if (t < 0.5) return interpolate("#BFE7FF", "#5B8DEF", t*2);
  return interpolate("#5B8DEF", "#22C55E", (t-0.5)*2);
};

export const VoiceSpectrumDisc: React.FC<Props> = ({ zones, baselineIPM, baselineEstablished }) => {
  // Processar dados: garantir 12 itens sempre
  const data = useMemo(() => {
    const arr = Array.isArray(zones) ? zones : [];
    return Array.from({ length: 12 }, (_, i) => {
      const z = arr.find(item => item.zone === i + 1);
      const val = typeof z?.deviation_score === "number" ? z.deviation_score : 0;
      return {
        id: i + 1,
        val,
        neg: NEGATIVES[i],
        pos: POSITIVES[i],
        hasData: !!z
      };
    });
  }, [zones]);

  // Calcular escala (Python: max_abs)
  const maxAbs = useMemo(() => {
    const maxVal = Math.max(...data.map(d => Math.abs(d.val)), 0.01);
    // Python usava o máximo absoluto dos dados. Aqui garantimos mínimo de 0.26 para não ficar muito zoomado se os dados forem pequenos
    return Math.max(maxVal, 0.26); 
  }, [data]);

  // Configurações Visuais (Traduzidas do Python para SVG)
  // Python: figsize=(15,8), xlim=(-0.45, 0.45)
  const W = 600, H = 480;
  const marginL = 160, marginR = 160, centerX = W / 2;
  const startY = 40, rowH = 32, gap = 4;
  
  // Função de escala X (Python: ax.set_xlim(-0.45, 0.45))
  const scaleX = (v: number) => centerX + (v / 0.45) * (W/2 - marginR);

  const blText = (baselineEstablished && baselineIPM) ? `${baselineIPM.toFixed(1)} IPM` : "CALIB...";

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-4 font-sans">
      {/* Títulos (Python: fig.text & ax.text headers) */}
      <div className="mb-4 border-b border-slate-100 pb-3">
        <h2 className="text-base font-bold text-slate-800">MAPA ZONAL DE PERCEPÇÃO FROID</h2>
        <p className="text-[10px] text-slate-500 mt-0.5">Índice de Desvio Multimodal — classificação negativa x positiva</p>
        
        <div className="flex justify-between items-end mt-4 px-2 relative">
          <span className="text-sm font-bold text-[#B91C1C]">NEGATIVOS</span>
          <div className="flex flex-col items-center pb-1">
             <span className="text-sm font-bold text-slate-800">DR</span>
             <span className="text-[10px] font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded mt-1">{blText}</span>
          </div>
          <span className="text-sm font-bold text-[#15803D]">POSITIVOS</span>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto overflow-visible">
        {/* Grid e Eixos (Python: ax.grid, ax.axvline) */}
        <line x1={centerX} y1={startY} x2={centerX} y2={H-40} stroke="#334155" strokeWidth="1.2" strokeDasharray="4 3" />
        
        {[ -0.3, -0.2, -0.1, 0.1, 0.2, 0.3 ].map(v => (
          <g key={v}>
            <line x1={scaleX(v)} y1={startY} x2={scaleX(v)} y2={H-40} stroke="#E5E7EB" strokeWidth="0.8" />
            <text x={scaleX(v)} y={H-25} textAnchor="middle" fontSize="8" fill="#94A3B8">{v.toFixed(1)}</text>
          </g>
        ))}
        <text x={centerX} y={H-25} textAnchor="middle" fontSize="8" fill="#94A3B8">0.0</text>

        {/* Barras e Textos (Python: for loop enumerate) */}
        {data.map((d, i) => {
          const y = startY + i * (rowH + gap) + rowH/2;
          const barColor = d.val < 0 ? getNegColor(d.val, maxAbs) : d.val > 0 ? getPosColor(d.val, maxAbs) : "#E2E8F0";
          const xEnd = scaleX(d.val);
          const isNeg = d.val < 0;
          
          // Tooltip Content
          const tip = (
            <div className="max-w-[240px] space-y-1">
              <p className="font-bold text-xs text-slate-900">Zona {d.id}: {d.hasData ? (isNeg ? d.neg : d.pos) : "Aguardando..."}</p>
              <p className="text-[10px] text-slate-600">IDM: {d.val.toFixed(2)}</p>
              <p className="text-[10px] text-slate-500 italic">{d.hasData ? (isNeg ? "Tendência negativa." : "Tendência positiva.") : "Sem dados suficientes."}</p>
            </div>
          );

          return (
            <FroidTooltip key={d.id} content={tip} width={260}>
              <g className="cursor-help hover:opacity-90 transition-opacity">
                {/* Barra (Python: ax.barh) */}
                <rect 
                  x={isNeg ? xEnd : centerX} 
                  y={y - 8} 
                  width={Math.abs(xEnd - centerX)} 
                  height={16} 
                  fill={barColor} 
                  rx="2"
                />
                
                {/* Número (Python: f"{i+1}.") */}
                <text x={marginL - 10} y={y+4} textAnchor="end" fontSize="10" fontWeight="bold" fill="#1E293B">{d.id}.</text>
                
                {/* Label Negativo (Python: ax.text esquerda) */}
                <text x={marginL} y={y+4} textAnchor="start" fontSize="10" fontWeight="bold" fill="#334155">{d.neg}</text>
                
                {/* Valor Numérico (Python: val na ponta) */}
                <text 
                  x={d.val === 0 ? centerX + 4 : (isNeg ? xEnd - 4 : xEnd + 4)} 
                  y={y+4} 
                  textAnchor={d.val <= 0 ? "end" : "start"} 
                  fontSize="9" fontWeight="bold" fill="#0F172A"
                >
                  {d.val >= 0 ? "+" : ""}{d.val.toFixed(2)}
                </text>

                {/* Label Positivo (Python: ax.text direita) */}
                <text x={W - marginR} y={y+4} textAnchor="end" fontSize="10" fontWeight="bold" fill="#334155">{d.pos}</text>
              </g>
            </FroidTooltip>
          );
        })}
      </svg>

      {/* Legenda (Python: legenda inferior) */}
      <div className="mt-4 flex justify-center gap-4 text-[10px] text-slate-600">
        <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#F7B7B7]"></span><span>Neg. Baixo</span></div>
        <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#B91C1C]"></span><span>Neg. Alto</span></div>
        <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#BFE7FF]"></span><span>Pos. Baixo</span></div>
        <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#22C55E]"></span><span>Pos. Alto</span></div>
      </div>
    </div>
  );
};
