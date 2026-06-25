import React, { useRef, useState } from "react";

interface TooltipProps {
  children: React.ReactNode;
  content: React.ReactNode;
  width?: number;
}

export function FroidTooltip({ children, content, width = 280 }: TooltipProps) {
  const [show, setShow] = useState(false);
  const anchorRef = useRef<HTMLSpanElement | null>(null);
  const rect = anchorRef.current?.getBoundingClientRect();
  const safeWidth = Math.min(width, typeof window !== "undefined" ? window.innerWidth - 24 : width);
  const left = rect
    ? Math.min(
        Math.max(12 + safeWidth / 2, rect.left + rect.width / 2),
        (typeof window !== "undefined" ? window.innerWidth : 1200) - 12 - safeWidth / 2,
      )
    : 0;
  const top = rect ? Math.max(12, rect.top - 10) : 0;

  return (
    <span
      ref={anchorRef}
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && rect && (
        <div
          className="fixed z-[9999] max-h-[70vh] max-w-[calc(100vw-24px)] -translate-x-1/2 -translate-y-full overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 text-[11px] leading-snug text-slate-700 shadow-xl"
          style={{ width: safeWidth, left, top }}
        >
          {content}
        </div>
      )}
    </span>
  );
}

export function ZoneTooltip({ zoneId, children }: { zoneId: number; children: React.ReactNode }) {
  const desc = {
    1: "Não Reconhecido vs. Autovalidação",
    2: "Pensamento Repetitivo vs. Pensamento Criativo e Independente",
    3: "Tristeza vs. Paz Interior",
    4: "Desconexão Emocional vs. Integração Emocional",
    5: "Autocrítica vs. Amor Próprio",
    6: "Amor Condicional vs. Amor Incondicional",
    7: "Raiva vs. Aceitação da Mudança",
    8: "Medo e Sobrecarga vs. Responsabilização",
    9: "Expressão Emocional Suprimida vs. Autoexpressão Adequada",
    10: "Indignidade vs. Autoaceitação",
    11: "Crenças Rígidas vs. Abertura às Possibilidades",
    12: "Crenças e Ações Conflitantes vs. Crenças e Ações Congruentes",
  }[zoneId] || "";

  return (
    <FroidTooltip
      content={
        <div className="space-y-1">
          <p className="font-bold text-slate-900">Zona {zoneId}</p>
          <p>{desc}</p>
          <p className="text-[10px] text-slate-400 uppercase tracking-wider">Clique para isolar</p>
        </div>
      }
    >
      {children}
    </FroidTooltip>
  );
}

export function ColorTooltip({ color, children }: { color: import("../../lib/froid-engine").FroidColor; children: React.ReactNode }) {
  const meanings: Record<string, string> = {
    BRANCO: "Zonas de compensação contendo menores quantidades de energia vocal (Offsetting)",
    AZUL: "Zona com baixo nível de desequilíbrio",
    VERDE: "Zona com nível médio de desequilíbrio",
    AMARELO: "Zona com alto nível de desequilíbrio",
    VERMELHO: "Zona com extremo nível de desequilíbrio",
    PRETO: "Excesso global de energia em toda a voz",
    CINZA: "Energia da voz normalizada/distribuída através de todas as zonas",
  };
  const hex: Record<string, string> = {
    BRANCO: "#f8fafc", AZUL: "#3b82f6", VERDE: "#22c55e", AMARELO: "#eab308", VERMELHO: "#ef4444", PRETO: "#0f172a", CINZA: "#6b7280",
  };

  return (
    <FroidTooltip
      content={
        <div className="space-y-1">
          <p className="font-bold" style={{ color: hex[color] || "#000" }}>{color}</p>
          <p>{meanings[color] || ""}</p>
        </div>
      }
    >
      {children}
    </FroidTooltip>
  );
}
