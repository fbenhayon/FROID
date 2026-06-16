import React from "react";
import { FroidTooltip } from "../ui/FroidTooltip";

export interface Commitment {
  model_id: number;
  title: string;
  zones: number[];
  theme: string;
}

export const COMMITMENT_TEXTS: Record<number, { title: string; lines: string[] }> = {
  1: {
    title: "1. COMPROMISSO GERAL",
    lines: [
      "Reconheço que sou responsável pelas escolhas que faço e pelos resultados que obtenho.",
      "Comprometo-me a abandonar comportamentos, pensamentos e atitudes que não contribuem para meu bem-estar.",
      "Escolho agir com maior consciência, honestidade e responsabilidade.",
      "Aceito que mudanças exigem esforço, persistência e paciência.",
      "A partir deste momento, autorizo-me a crescer e construir uma vida alinhada com meus valores."
    ]
  },
  2: {
    title: "2. RESPONSABILIDADE PESSOAL",
    lines: [
      "Reconheço que não posso mudar o passado, mas posso decidir como responderei a ele.",
      "Comprometo-me a parar de atribuir a outras pessoas a responsabilidade exclusiva pelos meus sentimentos.",
      "Assumo o compromisso de desenvolver autonomia emocional e maturidade.",
      "A partir de hoje, escolho agir como protagonista da minha própria história."
    ]
  },
  3: {
    title: "3. AUTOESTIMA E AUTOACEITAÇÃO",
    lines: [
      "Comprometo-me a tratar a mim mesmo com mais respeito, compreensão e compaixão.",
      "Reconheço meu valor como ser humano independentemente de erros ou opiniões externas.",
      "Escolho abandonar a autocrítica destrutiva e substituir julgamentos por aprendizado.",
      "A partir de agora, permito-me aceitar quem sou enquanto continuo evoluindo."
    ]
  },
  4: {
    title: "4. CONTROLE DA RAIVA E REATIVIDADE",
    lines: [
      "Reconheço que minhas emoções são importantes, mas não precisam controlar minhas ações.",
      "Comprometo-me a pausar antes de reagir impulsivamente.",
      "Escolho compreender minhas emoções, expressá-las de forma saudável e buscar soluções.",
      "A partir de hoje, transformo a energia da raiva em mudança construtiva."
    ]
  },
  5: {
    title: "5. LIBERTAÇÃO DE CRENÇAS LIMITANTES",
    lines: [
      "Reconheço que algumas crenças que carreguei até hoje podem não representar a realidade.",
      "Comprometo-me a questionar pensamentos automáticos, medos e limitações.",
      "Escolho abrir espaço para novas possibilidades, novos aprendizados e novas formas de enxergar a vida.",
      "A partir de agora, permito-me construir crenças mais saudáveis e fortalecedoras."
    ]
  },
  6: {
    title: "6. RELACIONAMENTOS SAUDÁVEIS",
    lines: [
      "Comprometo-me a comunicar minhas necessidades, sentimentos e limites de forma respeitosa e clara.",
      "Escolho construir relacionamentos baseados em respeito, reciprocidade e honestidade.",
      "Reconheço que não posso controlar os outros, mas posso escolher como me posiciono diante deles.",
      "A partir de hoje, buscarei conexões mais saudáveis e equilibradas."
    ]
  },
  7: {
    title: "7. MUDANÇA PROFUNDA",
    lines: [
      "Eu decido encerrar padrões antigos que já cumpriram sua função em minha vida.",
      "Reconheço que permanecer igual tem um custo maior do que mudar.",
      "Comprometo-me a agir diariamente em direção à pessoa que desejo me tornar.",
      "Escolho abandonar a autossabotagem, o medo excessivo e a procrastinação.",
      "A partir de agora, minha identidade deixa de ser definida pelos meus problemas e passa a ser definida pelos meus valores e potencial."
    ]
  },
};

interface Props { commitments: Commitment[]; }

export const CommitmentPanel: React.FC<Props> = ({ commitments }) => {
  const top3 = Array.isArray(commitments) ? commitments.slice(0, 3) : [];

  return (
    <div className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Declarações de Compromisso (Top 3)</span>
          <FroidTooltip content={
            <div className="max-w-[280px]">
              <p className="font-bold">Mapeamento FROID — Compromisso com a Mudança</p>
              <p className="text-[11px] mt-1">A cada 10 minutos, o sistema identifica as zonas de maior ativação e correlaciona com os 7 Modelos de Compromisso Terapêutico. Estes são apresentados ao profissional como norteadores de intervenção.</p>
            </div>
          } width={300}>
            <span className="cursor-help text-[10px] text-slate-400 border-b border-dashed border-slate-300">?</span>
          </FroidTooltip>
        </div>
        <span className="text-[9px] text-slate-400 font-mono">Atualizado a cada 10min</span>
      </div>

      {top3.length === 0 && (
        <p className="text-[10px] text-slate-400 italic py-2">Coletando padrões de ativação para sugerir modelos de compromisso...</p>
      )}

      {top3.map((c, i) => {
        const model = COMMITMENT_TEXTS[c.model_id];
        if (!model) return null;
        return (
          <div key={c.model_id} className={`rounded-lg border p-2.5 ${i === 0 ? "border-blue-200 bg-blue-50/60" : "border-slate-100 bg-slate-50/60"}`}>
            <div className="flex items-center justify-between mb-1">
              <p className="text-[10px] font-black text-slate-800 uppercase tracking-wide">{model.title}</p>
              <span className="text-[9px] font-bold text-slate-500 bg-white px-1.5 py-0.5 rounded border border-slate-100">Zonas: {c.zones.join(", ")}</span>
            </div>
            <p className="text-[10px] text-slate-600 leading-snug line-clamp-3">
              {model.lines[0]} {model.lines[1]}...
            </p>
            <FroidTooltip content={
              <div className="max-w-[320px] space-y-1">
                <p className="font-bold text-slate-900 text-xs">{model.title}</p>
                {model.lines.map((l, idx) => <p key={idx} className="text-slate-600 text-[11px] leading-snug">• {l}</p>)}
                <p className="text-[10px] text-slate-400 mt-1 pt-1 border-t border-slate-100">Baseado na ativação das zonas: {c.zones.join(", ")}</p>
              </div>
            } width={340}>
              <button className="mt-1 text-[9px] font-bold text-blue-600 hover:text-blue-800 cursor-pointer bg-transparent border-none p-0">
                Ler declaração completa →
              </button>
            </FroidTooltip>
          </div>
        );
      })}
    </div>
  );
};
