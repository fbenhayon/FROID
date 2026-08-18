import React from "react";
import { Link } from "react-router-dom";

import { apiUrl } from "../../lib/api";

/**
 * Peças comuns das telas de acesso.
 *
 * Vivem fora de LoginPage porque a verificação de e-mail e a recuperação de
 * senha são carregadas sob demanda, enquanto a tela de acesso entra no bundle
 * inicial. Se elas importassem da tela de acesso — ou o contrário — o
 * carregamento tardio deixaria de existir na prática.
 */

export const campoClasse =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none";

export const botaoClasse =
  "w-full rounded-lg bg-cyan-600 px-3 py-2 text-sm font-bold text-white hover:bg-cyan-500 disabled:opacity-60";

export const AccessCard: React.FC<{
  titulo: string;
  subtitulo?: string;
  children: React.ReactNode;
  rodape?: React.ReactNode;
}> = ({ titulo, subtitulo, children, rodape }) => (
  <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
    <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl">
      <div className="mb-6">
        <Link
          to="/"
          className="text-sm uppercase tracking-[0.3em] text-cyan-400 hover:text-cyan-300"
        >
          FROID
        </Link>
        <h1 className="mt-2 text-2xl font-bold">{titulo}</h1>
        {subtitulo && <p className="mt-2 text-sm text-slate-400">{subtitulo}</p>}
      </div>
      {children}
      {rodape}
    </div>
  </div>
);

export async function postAuthJson(path: string, body: Record<string, unknown>) {
  const res = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || "Não foi possível concluir a operação");
  return data;
}

/**
 * Link devolvido pela API quando não há SMTP e o modo de desenvolvimento está
 * ligado. Em produção nunca chega — e é por isso que aparece rotulado, para
 * ninguém confundir ambiente de teste com fluxo real.
 */
export const LinkDeDesenvolvimento: React.FC<{ link: string }> = ({ link }) =>
  link ? (
    <div className="mt-4 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
      <p className="text-[11px] font-black uppercase tracking-[0.2em] text-amber-400">
        Modo desenvolvimento — sem envio de e-mail
      </p>
      <a href={link} className="mt-1 block break-all text-xs text-amber-200 underline">
        {link}
      </a>
    </div>
  ) : null;
