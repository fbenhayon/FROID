import React from "react";
import { useNavigate } from "react-router-dom";

interface SettingsProps {
  user?: any;
}

export const Settings: React.FC<SettingsProps> = () => {
  const nav = useNavigate();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 p-8">
      <div className="max-w-4xl mx-auto bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
        <div>
          <h1 className="text-xl font-bold">Configurações Profissional</h1>
          <p className="text-sm text-slate-500 mt-1">
            Gestão clínica, consentimentos, agenda e auditoria do FROID.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="p-3 border border-slate-100 rounded-lg">
            <p className="text-sm font-semibold">Google OAuth e Agenda</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Conecte Google para sincronizar agenda, lembretes e cobrança de
              sessões.
            </p>
            <button className="mt-3 px-3 py-1.5 bg-slate-900 text-white rounded-lg text-xs font-bold">
              Conectar Google
            </button>
          </div>
          <div className="p-3 border border-slate-100 rounded-lg">
            <p className="text-sm font-semibold">Consentimentos LGPD</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Aceite granular v2.0 com quarentena e exclusão sob aprovação do
              DPO.
            </p>
            <div className="mt-3 text-[11px] text-slate-600">
              ✓ Pesquisa anônima ativada · ✓ Compartilhamento com terceiros
              desativado
            </div>
          </div>
          <div className="p-3 border border-slate-100 rounded-lg">
            <p className="text-sm font-semibold">Planos e Cobrança</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Essencial, Profissional e Premium com Stripe, PIX e emissão de
              nota fiscal.
            </p>
            <div className="mt-3 flex gap-2 text-[11px]">
              <span className="rounded-full bg-blue-50 text-blue-700 px-2 py-0.5">
                Essencial
              </span>
              <span className="rounded-full bg-violet-50 text-violet-700 px-2 py-0.5">
                Profissional
              </span>
              <span className="rounded-full bg-emerald-50 text-emerald-700 px-2 py-0.5">
                Premium
              </span>
            </div>
          </div>
          <div className="p-3 border border-slate-100 rounded-lg">
            <p className="text-sm font-semibold">Auditoria e Ledger</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Hash chain local para consentimentos, exclusão e acesso às
              sessões.
            </p>
            <div className="mt-3 text-[11px] text-slate-600">
              • SHA256 · • 90 dias de purga · • DPO-admin
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
          <p className="text-sm font-semibold">Faixas de valor por sessão</p>
          <div className="mt-3 grid md:grid-cols-3 gap-3 text-[11px] text-slate-600">
            <div className="rounded-lg bg-white p-3 border border-slate-200">
              Faixa 1 · R$ 30,00
            </div>
            <div className="rounded-lg bg-white p-3 border border-slate-200">
              Faixa 2 · R$ 60,00
            </div>
            <div className="rounded-lg bg-white p-3 border border-slate-200">
              Faixa 3 · R$ 90,00
            </div>
          </div>
        </div>

        <button
          onClick={() => nav("/dashboard")}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  );
};
