import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import {
  createProfessionalPrompt,
  loadProfessionalPrompts,
  saveProfessionalPrompts,
  type ProfessionalPrompt,
} from "../lib/professional-prompts";

interface SettingsProps {
  user?: FroidUser | null;
}

export const Settings: React.FC<SettingsProps> = ({ user }) => {
  const nav = useNavigate();
  const ownerEmail = useMemo(() => user?.email || "", [user?.email]);
  const [prompts, setPrompts] = useState<ProfessionalPrompt[]>([]);
  const [promptTitle, setPromptTitle] = useState("");
  const [promptText, setPromptText] = useState("");
  const [savedMessage, setSavedMessage] = useState("");

  useEffect(() => {
    setPrompts(loadProfessionalPrompts(ownerEmail));
  }, [ownerEmail]);

  const addPrompt = (event: React.FormEvent) => {
    event.preventDefault();
    const title = promptTitle.trim();
    const text = promptText.trim();
    if (!title || !text) return;

    const next = [createProfessionalPrompt(title, text), ...prompts].slice(0, 40);
    setPrompts(next);
    saveProfessionalPrompts(ownerEmail, next);
    setPromptTitle("");
    setPromptText("");
    setSavedMessage("Prompt do profissional salvo.");
    window.setTimeout(() => setSavedMessage(""), 2500);
  };

  const removePrompt = (promptId: string) => {
    const next = prompts.filter((prompt) => prompt.id !== promptId);
    setPrompts(next);
    saveProfessionalPrompts(ownerEmail, next);
    setSavedMessage("Prompt removido.");
    window.setTimeout(() => setSavedMessage(""), 2500);
  };

  return (
    <div className="min-h-screen bg-slate-50 p-8 text-slate-800">
      <div className="mx-auto max-w-5xl space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">Configuracoes do Profissional</h1>
            <p className="mt-1 text-sm text-slate-500">
              Gestao clinica, consentimentos, agenda, auditoria e prompts proprios do FROID Explica.
            </p>
          </div>
          {ownerEmail && (
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
              {ownerEmail}
            </span>
          )}
        </div>

        <section className="rounded-xl border border-cyan-100 bg-cyan-50/60 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-cyan-950">Prompts proprios do profissional</p>
              <p className="mt-1 text-xs leading-5 text-cyan-800">
                Estes prompts aparecem separados dos prompts nativos no dropdown do FROID Explica.
                Eles ficam vinculados ao e-mail do profissional neste navegador.
              </p>
            </div>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-cyan-800">
              {prompts.length} personalizados
            </span>
          </div>

          <form onSubmit={addPrompt} className="mt-4 grid gap-3">
            <label>
              <span className="text-xs font-bold uppercase tracking-wide text-cyan-900">
                Titulo curto
              </span>
              <input
                value={promptTitle}
                onChange={(event) => setPromptTitle(event.target.value)}
                placeholder="Ex: Risco familiar recente"
                className="mt-1 w-full rounded-lg border border-cyan-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500"
                maxLength={90}
              />
            </label>
            <label>
              <span className="text-xs font-bold uppercase tracking-wide text-cyan-900">
                Prompt completo
              </span>
              <textarea
                value={promptText}
                onChange={(event) => setPromptText(event.target.value)}
                placeholder="Escreva a pergunta ou comando que deseja reutilizar no FROID Explica..."
                rows={4}
                className="mt-1 w-full rounded-lg border border-cyan-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500"
              />
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <button
                disabled={!promptTitle.trim() || !promptText.trim()}
                className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-bold text-white hover:bg-cyan-800 disabled:opacity-40"
              >
                Salvar prompt
              </button>
              {savedMessage && <span className="text-xs font-bold text-cyan-800">{savedMessage}</span>}
            </div>
          </form>

          {prompts.length > 0 && (
            <div className="mt-4 divide-y divide-cyan-100 rounded-lg border border-cyan-100 bg-white">
              {prompts.map((prompt) => (
                <div key={prompt.id} className="grid gap-2 p-3 md:grid-cols-[1fr_auto]">
                  <div>
                    <p className="text-sm font-bold text-slate-900">{prompt.title}</p>
                    <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-slate-600">
                      {prompt.text}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removePrompt(prompt.id)}
                    className="h-fit rounded-lg border border-red-200 px-3 py-1.5 text-xs font-bold text-red-600 hover:bg-red-50"
                  >
                    Excluir
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-slate-100 p-3">
            <p className="text-sm font-semibold">Google OAuth e Agenda</p>
            <p className="mt-1 text-xs text-slate-400">
              Conecte Google para sincronizar agenda, lembretes e cobranca de sessoes.
            </p>
            <button className="mt-3 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-bold text-white">
              Conectar Google
            </button>
          </div>
          <div className="rounded-lg border border-slate-100 p-3">
            <p className="text-sm font-semibold">Consentimentos LGPD</p>
            <p className="mt-1 text-xs text-slate-400">
              Aceite granular com quarentena e exclusao sob aprovacao do DPO.
            </p>
            <div className="mt-3 text-xs text-slate-600">
              Pesquisa anonima ativada - Compartilhamento com terceiros desativado
            </div>
          </div>
          <div className="rounded-lg border border-slate-100 p-3">
            <p className="text-sm font-semibold">Planos e Cobranca</p>
            <p className="mt-1 text-xs text-slate-400">
              Checkout Stripe e controle de creditos de sessao FROID.
            </p>
            <div className="mt-3 flex gap-2 text-xs">
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">
                Sessao avulsa
              </span>
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700">
                Pacote 25
              </span>
            </div>
          </div>
          <div className="rounded-lg border border-slate-100 p-3">
            <p className="text-sm font-semibold">Auditoria e Ledger</p>
            <p className="mt-1 text-xs text-slate-400">
              Hash chain local para consentimentos, exclusao e acesso as sessoes.
            </p>
            <div className="mt-3 text-xs text-slate-600">
              SHA256 - 90 dias de purga - DPO-admin
            </div>
          </div>
        </div>

        <button
          onClick={() => nav("/dashboard")}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700"
        >
          Voltar ao Dashboard
        </button>
      </div>
    </div>
  );
};
