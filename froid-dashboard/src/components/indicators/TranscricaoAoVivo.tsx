// A fala da sessão, na ordem em que aconteceu, com quem falou.
//
// Por que existe: o sistema já transcrevia os dois canais separadamente e já
// marcava cada linha com `DR. - ` ou `PC - `. As linhas eram acumuladas em
// `transcriptLinesRef`, havia até um limite chamado MAX_VISIBLE_TRANSCRIPT_LINES
// — e nada as renderizava. O nome prometia uma visibilidade que não existia.
//
// O profissional conduzia a sessão sem ver o que o sistema estava ouvindo. E
// quando o Bruno apontou quatro erros no relatório dele, três eram de
// transcrição: ninguém tinha como perceber durante a consulta, porque a
// transcrição só aparecia depois, dentro do resumo já redigido.
//
// Ver a fala enquanto ela acontece é o que permite corrigir no ato.

import React, { useEffect, useRef } from "react";

type Props = {
  /** Linhas já prefixadas com `DR. - ` ou `PC - `, em ordem cronológica. */
  linhas: string[];
};

const PREFIXO = /^(DR\.\s*-\s*|PC\s*-\s*|PAC\s*-\s*)/i;

/** Separa o rótulo do que foi dito. O prefixo é convenção de armazenamento;
 *  na tela ele vira cor e posição, que se leem mais rápido que texto. */
function partir(linha: string): { quem: "DR" | "PC"; fala: string } {
  const casa = linha.match(PREFIXO);
  const bruto = (casa?.[1] || "").toUpperCase();
  return {
    quem: bruto.startsWith("DR") ? "DR" : "PC",
    fala: linha.replace(PREFIXO, "").trim(),
  };
}

export const TranscricaoAoVivo: React.FC<Props> = ({ linhas }) => {
  const fim = useRef<HTMLDivElement | null>(null);

  // Rola sozinho para a última fala. Sem isto, a transcrição "ao vivo" exigiria
  // que o profissional rolasse a cada frase — durante o atendimento, ninguém o
  // faria, e o painel voltaria a ser decorativo.
  useEffect(() => {
    fim.current?.scrollIntoView({ block: "end" });
  }, [linhas.length]);

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 px-2 py-2">
      <div className="mb-1 flex shrink-0 items-center justify-between border-b border-slate-800 pb-1">
        <span className="text-[10px] font-black uppercase tracking-widest text-slate-100">
          Transcrição da sessão
        </span>
        <span className="flex items-center gap-2 text-[8px] font-bold uppercase tracking-wide">
          <span className="flex items-center gap-1 text-sky-300">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-sky-400" />
            DR profissional
          </span>
          <span className="flex items-center gap-1 text-emerald-300">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
            PC paciente
          </span>
        </span>
      </div>

      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
        {!linhas.length && (
          <p className="pt-4 text-center text-[11px] italic text-slate-500">
            Aguardando a primeira fala.
          </p>
        )}
        {linhas.map((linha, indice) => {
          const { quem, fala } = partir(linha);
          if (!fala) return null;
          const doProfissional = quem === "DR";
          return (
            <div
              key={`${indice}-${fala.slice(0, 24)}`}
              className={`rounded border-l-2 px-2 py-1 ${
                doProfissional
                  ? "border-sky-500 bg-sky-950/30"
                  : "border-emerald-500 bg-emerald-950/30"
              }`}
            >
              <span
                className={`mr-1.5 text-[9px] font-black uppercase ${
                  doProfissional ? "text-sky-300" : "text-emerald-300"
                }`}
              >
                {doProfissional ? "DR" : "PC"}
              </span>
              <span className="text-[11px] leading-5 text-slate-200">{fala}</span>
            </div>
          );
        })}
        <div ref={fim} />
      </div>
    </div>
  );
};
