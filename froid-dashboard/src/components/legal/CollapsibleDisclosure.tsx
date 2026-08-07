import React from "react";

// Apresenta um bloco de compliance por TITULO, com o descritivo integral a um
// clique. O conteudo continua na pagina — nao vai para outra rota nem depende
// de rede — porque a LGPD exige que a informacao esteja acessivel, e nao que
// esteja empilhada na frente de quem esta preenchendo o cadastro.
//
// <details> foi escolhido de proposito: o navegador ja resolve teclado, leitor
// de tela e "buscar na pagina" (Chrome e Firefox abrem o bloco fechado quando o
// termo esta la dentro). Uma div com useState perderia as tres coisas.

type Props = {
  title: string;
  /** Uma linha explicando o que ha dentro, visivel com o bloco fechado. */
  summary?: string;
  /** Rotulo do link de abertura. */
  action?: string;
  defaultOpen?: boolean;
  className?: string;
  children: React.ReactNode;
};

export const CollapsibleDisclosure: React.FC<Props> = ({
  title,
  summary,
  action = "ver descritivo",
  defaultOpen = false,
  className = "",
  children,
}) => (
  <details
    open={defaultOpen}
    className={`group rounded-lg border border-slate-700 bg-slate-950 ${className}`}
  >
    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-3 outline-none focus-visible:ring-2 focus-visible:ring-cyan-500">
      <span className="text-xs font-black leading-5 text-slate-200">{title}</span>
      <span className="shrink-0 text-[11px] font-bold text-cyan-200 underline">
        <span className="group-open:hidden">{action}</span>
        <span className="hidden group-open:inline">recolher</span>
      </span>
    </summary>
    {summary && (
      <p className="px-3 pb-1 text-[11px] leading-5 text-slate-400">{summary}</p>
    )}
    <div className="p-3 pt-2">{children}</div>
  </details>
);
