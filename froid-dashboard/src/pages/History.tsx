import React from "react";

interface HistoryProps {
  user?: any;
}
import { useNavigate } from "react-router-dom";

export const History: React.FC<HistoryProps> = () => {
  const nav = useNavigate();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <div className="max-w-4xl mx-auto bg-slate-900 rounded-xl border border-slate-700 shadow-sm p-6">
        <h1 className="text-xl font-bold mb-4">Histórico de Sessões</h1>
        <p className="text-sm text-slate-400 mb-6">
          Prontuário criptografado FROID — acesso auditado.
        </p>
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="flex items-center justify-between p-3 rounded-lg border border-slate-700 hover:bg-slate-950"
            >
              <div>
                <p className="text-sm font-semibold">
                  Sessão #{9000 + i} — Paciente Anônimo
                </p>
                <p className="text-[11px] text-slate-400">
                  IPM: 58.3 • Coerência: ALTA • 45min
                </p>
              </div>
              <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-emerald-100 text-emerald-200">
                Arquivada
              </span>
            </div>
          ))}
        </div>
        <button
          onClick={() => nav("/dashboard")}
          className="mt-6 px-4 py-2 bg-cyan-700 text-white rounded-lg text-sm font-bold hover:bg-cyan-800"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  );
};


