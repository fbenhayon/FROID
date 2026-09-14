import React from "react";

/**
 * Um indice, um painel: valor atual, referencia, delta, faixa e a linha.
 *
 * Nasceu dentro de SessionReport e vive aqui porque a tela do PACIENTE
 * passou a usar o mesmo desenho. A copia seria a quarta desta semana neste
 * projeto, e as tres anteriores divergiram — ver _report_within_context no
 * backend.
 *
 * O que o desenho afirma, e que a versao antiga da tela do paciente nao
 * afirmava: cada serie tem escala PROPRIA. Sobrepor indices de grandezas
 * diferentes num eixo so — IPM perto de 50, IDM perto de 0,04 — achata as
 * duas e o olho le estabilidade onde nao ha medida comparavel.
 *
 * E ausencia continua ausencia: valor nulo abre buraco na linha, e serie sem
 * nenhuma leitura mostra o aviso em vez de um grafico rente ao zero.
 */

export type SerieEvolucao = {
  key: string;
  label: string;
  color: string;
  valores: Array<number | null>;
  /** O valor de referencia desta serie. */
  referencia: number | null;
  /** Como a referencia se chama na tela: "baseline", "1a sessao"... */
  referenciaRotulo: string;
  casas: number;
};

export const PainelEvolucao: React.FC<{
  serie: SerieEvolucao;
  rotulos: string[];
  /** Titulo do painel. Quem tem verbete de ajuda passa o proprio componente. */
  titulo?: React.ReactNode;
}> = ({ serie, rotulos, titulo }) => {
  const validos = serie.valores.filter(
    (v): v is number => typeof v === "number" && Number.isFinite(v),
  );

  if (!validos.length) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-950 p-3">
        <div className="flex items-baseline justify-between gap-2">
          {titulo ?? serie.label}
          <span className="text-[10px] text-slate-500">sem leitura</span>
        </div>
        <p className="mt-2 text-[10px] italic leading-4 text-slate-500">
          Nenhum corte deste período produziu valor para este índice. O gráfico
          fica vazio de propósito: uma linha no zero pareceria medição.
        </p>
      </div>
    );
  }

  const menor = Math.min(...validos);
  const maior = Math.max(...validos);
  const semVariacao = maior - menor < 1e-9;
  // Folga de 15% para a linha não encostar nas bordas; série constante ganha
  // uma janela artificial para não virar divisão por zero.
  const folga = semVariacao ? Math.max(1, Math.abs(maior) * 0.1) : (maior - menor) * 0.15;
  const min = menor - folga;
  const max = maior + folga;

  const W = 300;
  const H = 64;
  const x = (i: number) =>
    serie.valores.length <= 1 ? W / 2 : (i / (serie.valores.length - 1)) * W;
  const y = (v: number) => H - ((v - min) / Math.max(1e-9, max - min)) * H;

  const pontos = serie.valores
    .map((v, i) =>
      v === null || v === undefined || !Number.isFinite(v)
        ? null
        : `${x(i).toFixed(1)},${y(v).toFixed(1)}`,
    )
    .filter(Boolean)
    .join(" ");

  const atual = validos[validos.length - 1];
  const base = serie.referencia;
  const temBase = typeof base === "number" && Number.isFinite(base);
  const delta = temBase ? atual - (base as number) : null;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-950 p-3">
      <div className="flex items-baseline justify-between gap-2">
        {titulo ?? serie.label}
        <span className="font-mono text-[13px] font-black" style={{ color: serie.color }}>
          {atual.toFixed(serie.casas)}
        </span>
      </div>

      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-[9px] text-slate-400">
        <span>
          {serie.referenciaRotulo}{" "}
          <strong className="font-mono text-slate-200">
            {temBase ? (base as number).toFixed(serie.casas) : "--"}
          </strong>
        </span>
        {delta !== null && (
          <span>
            delta{" "}
            <strong
              className={`font-mono ${delta > 0 ? "text-amber-300" : delta < 0 ? "text-cyan-300" : "text-slate-300"}`}
            >
              {delta > 0 ? "+" : ""}
              {delta.toFixed(serie.casas)}
            </strong>
          </span>
        )}
        <span>
          faixa{" "}
          <strong className="font-mono text-slate-200">
            {menor.toFixed(serie.casas)} a {maior.toFixed(serie.casas)}
          </strong>
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 h-16 w-full" preserveAspectRatio="none">
        {temBase && (base as number) >= min && (base as number) <= max && (
          <line
            x1={0}
            x2={W}
            y1={y(base as number)}
            y2={y(base as number)}
            stroke="#64748b"
            strokeDasharray="4 4"
            strokeWidth={1}
          />
        )}
        <polyline
          points={pontos}
          fill="none"
          stroke={serie.color}
          strokeWidth={2.5}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        {serie.valores.map((v, i) =>
          v === null || v === undefined || !Number.isFinite(v) ? null : (
            <circle key={i} cx={x(i)} cy={y(v)} r={2.5} fill={serie.color} />
          ),
        )}
      </svg>

      <div className="mt-1 flex justify-between text-[8px] text-slate-500">
        <span>{rotulos[0]}</span>
        <span>{rotulos[rotulos.length - 1]}</span>
      </div>

      {semVariacao && (
        <p className="mt-1 text-[9px] italic text-slate-500">
          Sem variação entre os cortes.
        </p>
      )}
    </div>
  );
};
