import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";

type PrivacyRequest = {
  id: string;
  organization_name: string;
  request_type: string;
  status: string;
  request_payload?: { details?: string; details_locked?: boolean };
  response_summary?: string;
  legal_basis?: string;
  retention_exception?: string;
  submitted_at: string;
  service_due_at: string;
};

type PrivacyResponseForm = {
  status: string;
  response_summary: string;
  legal_basis: string;
  retention_exception: string;
};

const RESPONSE_FIELDS: Array<{
  field: keyof Omit<PrivacyResponseForm, "status">;
  label: string;
  rows: number;
}> = [
  { field: "response_summary", label: "Resposta ao titular", rows: 4 },
  { field: "legal_basis", label: "Fundamento aplicável", rows: 2 },
  { field: "retention_exception", label: "Exceção de retenção, se houver", rows: 2 },
];

const STATUS_OPTIONS = [
  "identity_verified", "in_review", "awaiting_information", "approved",
  "partially_approved", "denied", "completed", "cancelled",
];

export const PrivacyRequests: React.FC<{ user: FroidUser | null }> = ({ user }) => {
  const nav = useNavigate();
  const organizationId = user?.active_organization_id || user?.organizations?.[0]?.organization_id || "";
  const [items, setItems] = useState<PrivacyRequest[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [form, setForm] = useState<PrivacyResponseForm>({
    status: "in_review",
    response_summary: "",
    legal_basis: "",
    retention_exception: "",
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const headers = useMemo(() => {
    const token = window.localStorage.getItem("froid_token") || "";
    return {
      Authorization: `Bearer ${token}`,
      "X-FROID-Organization-ID": organizationId,
    };
  }, [organizationId]);

  const load = useCallback(async () => {
    if (!organizationId) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/organizations/${organizationId}/privacy-requests`), { headers });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível carregar a fila LGPD.");
      setItems(Array.isArray(data.requests) ? data.requests : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar solicitações LGPD.");
    } finally {
      setLoading(false);
    }
  }, [headers, organizationId]);

  useEffect(() => { void load(); }, [load]);

  const selected = items.find((item) => item.id === selectedId) || null;

  const choose = (item: PrivacyRequest) => {
    setSelectedId(item.id);
    setForm({
      status: item.status === "identity_verified" ? "in_review" : item.status,
      response_summary: item.response_summary || "",
      legal_basis: item.legal_basis || "",
      retention_exception: item.retention_exception || "",
    });
    setMessage("");
    setError("");
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/privacy-requests/${selected.id}`),
        {
          method: "PATCH",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify(form),
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível registrar a decisão.");
      setMessage("Andamento registrado e auditado.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar solicitação LGPD.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <main className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">Governança e LGPD</p>
            <h1 className="mt-2 text-2xl font-black text-white">Solicitações dos titulares</h1>
            <p className="mt-2 text-sm text-slate-400">Fila protegida da organização ativa. Todas as mudanças ficam auditadas.</p>
          </div>
          <button onClick={() => nav("/settings")} className="rounded border border-slate-700 px-4 py-2 text-xs font-black hover:bg-slate-900">
            Voltar às configurações
          </button>
        </header>

        {error && <p className="mt-4 rounded border border-red-900 bg-red-950 p-3 text-xs font-bold text-red-200">{error}</p>}
        {message && <p className="mt-4 rounded border border-emerald-900 bg-emerald-950 p-3 text-xs font-bold text-emerald-200">{message}</p>}

        <div className="mt-5 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-black">Fila de atendimento</h2>
              <button onClick={() => void load()} className="text-xs font-bold text-cyan-300">Atualizar</button>
            </div>
            <div className="mt-3 space-y-2">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => choose(item)}
                  className={`w-full rounded border p-3 text-left text-xs ${selectedId === item.id ? "border-cyan-500 bg-cyan-950" : "border-slate-700 bg-slate-950 hover:border-slate-500"}`}
                >
                  <div className="flex justify-between gap-3">
                    <p className="font-black text-white">{item.request_type.replace(/_/g, " ")}</p>
                    <span className="uppercase text-cyan-200">{item.status.replace(/_/g, " ")}</span>
                  </div>
                  <p className="mt-2 text-slate-400">Prazo: {new Date(item.service_due_at).toLocaleString("pt-BR")}</p>
                </button>
              ))}
              {!items.length && !loading && <p className="rounded bg-slate-950 p-4 text-xs text-slate-400">Nenhuma solicitação pendente.</p>}
              {loading && <p className="text-xs font-bold text-cyan-300">Carregando...</p>}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            {!selected ? (
              <p className="text-sm text-slate-400">Selecione uma solicitação para analisar e registrar a resposta.</p>
            ) : (
              <form onSubmit={save}>
                <h2 className="text-sm font-black text-white">Análise do protocolo</h2>
                <p className="mt-1 break-all text-[10px] text-slate-500">{selected.id}</p>
                <div className="mt-3 rounded border border-slate-700 bg-slate-950 p-3 text-xs leading-5 text-slate-300">
                  {selected.request_payload?.details || "Titular não acrescentou detalhes."}
                </div>
                <label className="mt-3 block text-[10px] font-bold uppercase text-slate-400">Status
                  <select value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white">
                    {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status.replace(/_/g, " ")}</option>)}
                  </select>
                </label>
                {RESPONSE_FIELDS.map(({ field, label, rows }) => (
                  <label key={field} className="mt-3 block text-[10px] font-bold uppercase text-slate-400">{label}
                    <textarea value={form[field]} onChange={(event) => setForm((current) => ({ ...current, [field]: event.target.value }))} rows={rows} className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs normal-case text-white" />
                  </label>
                ))}
                <button disabled={loading} className="mt-4 rounded bg-cyan-600 px-4 py-2 text-xs font-black text-white disabled:opacity-50">
                  Registrar andamento
                </button>
              </form>
            )}
          </section>
        </div>
      </main>
    </div>
  );
};
