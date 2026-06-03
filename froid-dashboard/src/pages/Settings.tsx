import React from "react";
import { useNavigate } from "react-router-dom";

export const Settings: React.FC = () => {
  const nav = useNavigate();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 p-8">
      <div className="max-w-2xl mx-auto bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <h1 className="text-xl font-bold mb-4">Configurações Profissional</h1>
        <div className="space-y-4">
          <div className="p-3 border border-slate-100 rounded-lg">
            <p className="text-sm font-semibold">Sincronização Google Agenda</p>
            <p className="text-[11px] text-slate-400 mt-1">Status: Não conectado. Em desenvolvimento.</p>
          </div>
          <div className="p-3 border border-slate-100 rounded-lg">
            <p className="text-sm font-semibold">Planos de Sessão (Valores A/B/C)</p>
            <p className="text-[11px] text-slate-400 mt-1">Em desenvolvimento.</p>
          </div>
          <div className="p-3 border border-slate-100 rounded-lg">
            <p className="text-sm font-semibold">Credenciais Clínicas</p>
            <p className="text-[11px] text-slate-400 mt-1">Verificação em andamento.</p>
          </div>
        </div>
        <button onClick={() => nav("/dashboard")} className="mt-6 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700">Voltar ao Dashboard</button>
      </div>
    </div>
  );
};
