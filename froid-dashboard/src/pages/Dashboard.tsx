import React from "react";
import { useNavigate } from "react-router-dom";

function makeId() {
  return "froid-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

export const Dashboard: React.FC = () => {
  const nav = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm">F</div>
          <h1 className="text-lg font-bold tracking-tight">FROID <span className="text-slate-400 font-normal">| Dashboard Profissional</span></h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">Dr. Profissional</span>
          <div className="h-8 w-8 rounded-full bg-slate-200" />
        </div>
      </header>

      <main className="p-6 max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <button
            onClick={() => nav(`/session/${makeId()}`)}
            className="text-left bg-blue-600 hover:bg-blue-700 text-white p-5 rounded-xl shadow-sm transition-colors"
          >
            <div className="text-2xl mb-1">➕</div>
            <h2 className="font-bold text-sm uppercase tracking-wide">Nova Sessão</h2>
            <p className="text-[11px] opacity-80 mt-1">Iniciar avaliação multimodal com captura bioacústica e facial.</p>
          </button>

          <button
            onClick={() => nav("/history")}
            className="text-left bg-white hover:bg-slate-50 p-5 rounded-xl border border-slate-200 shadow-sm transition-colors"
          >
            <div className="text-2xl mb-1">📁</div>
            <h2 className="font-bold text-sm uppercase tracking-wide text-slate-700">Histórico</h2>
            <p className="text-[11px] text-slate-500 mt-1">12 sessões arquivadas (prontuário criptografado).</p>
          </button>

          <button
            onClick={() => nav("/settings")}
            className="text-left bg-white hover:bg-slate-50 p-5 rounded-xl border border-slate-200 shadow-sm transition-colors"
          >
            <div className="text-2xl mb-1">⚙️</div>
            <h2 className="font-bold text-sm uppercase tracking-wide text-slate-700">Configurações</h2>
            <p className="text-[11px] text-slate-500 mt-1">Agenda Google, planos de sessão e credenciais.</p>
          </button>
        </div>

        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Sessões Recentes</h3>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="divide-y divide-slate-100">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-center justify-between p-4 hover:bg-slate-50 transition-colors cursor-pointer" onClick={() => nav("/history")}>
                <div>
                  <p className="text-sm font-semibold text-slate-700">Paciente Anônimo #{9821 + i}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">{new Date(Date.now() - i * 86400000).toLocaleDateString("pt-BR")} • Duração 47min • IPM médio 62.4</p>
                </div>
                <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-emerald-100 text-emerald-700">Finalizada</span>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
};
