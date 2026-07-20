import React, { useCallback, useEffect, useState } from "react";
import { apiUrl } from "../../lib/api";

type ReceivableRow = {
  patient_key: string;
  patient?: { name?: string; email?: string; phone?: string; document?: string };
  session_count: number;
  package_count: number;
  single_count: number;
  total_due_brl: string;
  total_received_brl: string;
  total_pending_brl: string;
  last_invite_at: string;
  status: string;
  items?: Array<{
    session_id?: string;
    invite_id?: string;
    accepted_at?: string;
    created_at?: string;
    due_brl?: string;
    received_brl?: string;
    payment_status?: string;
  }>;
};

type ReceivablesSummary = {
  total_due_brl: string;
  total_received_brl: string;
  total_pending_brl: string;
};

const statusStyle: Record<string, string> = {
  recebido: "border-emerald-700 bg-emerald-950 text-emerald-200",
  parcial: "border-amber-700 bg-amber-950 text-amber-100",
  pendente: "border-red-700 bg-red-950 text-red-100",
  sem_valor: "border-slate-700 bg-slate-950 text-slate-300",
};

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("froid_token") || "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function escapeHtml(value: unknown) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function openReceipt(row: ReceivableRow) {
  // Abra a janela enquanto o clique ainda é o gesto ativo do usuário. Se a
  // referência for solicitada antes, navegadores móveis podem bloquear o recibo.
  const receiptWindow = window.open("", "_blank", "width=920,height=720");
  if (!receiptWindow) {
    window.alert("Não foi possível abrir o recibo. Verifique o bloqueador de pop-ups.");
    return;
  }
  receiptWindow.document.open();
  receiptWindow.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8" />
    <title>FROID — Preparando recibo</title></head><body style="font-family:Arial,sans-serif;padding:32px;color:#0f172a">
    <p>Preparando recibo do paciente…</p></body></html>`);
  receiptWindow.document.close();

  const reference = window.prompt(
    "Referência oficial Receita Saúde/NFS-e, se houver:",
    "",
  ) || "--";
  const issuedAt = new Date().toLocaleDateString("pt-BR");
  const rows = (row.items?.length ? row.items : [{}]).map((item) => `
    <tr>
      <td>${escapeHtml(item.session_id || item.invite_id || row.patient_key)}</td>
      <td>${escapeHtml(item.accepted_at || item.created_at ? new Date(item.accepted_at || item.created_at || "").toLocaleDateString("pt-BR") : "--")}</td>
      <td>${escapeHtml(item.due_brl || row.total_due_brl)}</td>
      <td>${escapeHtml(item.received_brl || row.total_received_brl)}</td>
      <td>${escapeHtml(item.payment_status || row.status)}</td>
    </tr>
  `).join("");
  receiptWindow.document.open();
  receiptWindow.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8" />
    <title>FROID — Recibo</title><style>
    body{color:#0f172a;font-family:Arial,sans-serif;margin:32px}h1{color:#0e7490;font-size:22px}
    .meta{display:grid;gap:8px;grid-template-columns:1fr 1fr;margin:20px 0}table{border-collapse:collapse;width:100%}
    th,td{border:1px solid #cbd5e1;font-size:12px;padding:8px;text-align:left}th{background:#e2e8f0}
    .totals{display:flex;gap:24px;justify-content:flex-end;margin-top:16px;font-weight:700}.note{color:#475569;font-size:11px;margin-top:28px}
    @media print{button{display:none}}</style></head><body>
    <button onclick="window.print()">Imprimir / salvar PDF</button><h1>FROID — Fatura/recibo de atendimento</h1>
    <div class="meta"><div><b>Paciente:</b> ${escapeHtml(row.patient?.name || "--")}</div><div><b>Documento:</b> ${escapeHtml(row.patient?.document || "--")}</div>
    <div><b>Emissão:</b> ${escapeHtml(issuedAt)}</div><div><b>Referência oficial:</b> ${escapeHtml(reference)}</div></div>
    <table><thead><tr><th>ID FROID</th><th>Data</th><th>Devido</th><th>Recebido</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="totals"><span>Devido: ${escapeHtml(row.total_due_brl)}</span><span>Recebido: ${escapeHtml(row.total_received_brl)}</span><span>Pendente: ${escapeHtml(row.total_pending_brl)}</span></div>
    <p class="note">Documento operacional. A emissão fiscal oficial deve seguir as obrigações aplicáveis ao prestador.</p>
    </body></html>`);
  receiptWindow.document.close();
  receiptWindow.focus();
  void fetch(apiUrl("/api/audit/client-event"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      action: "receipt.export",
      resource_id: row.items?.[0]?.session_id || row.patient_key,
      surface: "administrative_receivables",
    }),
  }).catch(() => undefined);
}

export const ProfessionalReceivables: React.FC = () => {
  const [rows, setRows] = useState<ReceivableRow[]>([]);
  const [summary, setSummary] = useState<ReceivablesSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(apiUrl("/api/professional/receivables"), {
        headers: authHeaders(),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Falha ao carregar recebimentos.");
      setRows(Array.isArray(data?.rows) ? data.rows : []);
      setSummary(data?.summary || null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Falha ao carregar recebimentos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => void load(), [load]);

  const update = async (
    patientKey: string,
    action: "paid" | "pending" | "partial",
  ) => {
    setMessage("");
    let receivedCents: number | undefined;
    if (action === "partial") {
      const typed = window.prompt("Valor recebido parcialmente em R$:", "");
      if (!typed) return;
      receivedCents = Math.round(Number(typed.replace(/\./g, "").replace(",", ".")) * 100);
      if (!Number.isFinite(receivedCents) || receivedCents < 0) {
        setMessage("Valor parcial inválido.");
        return;
      }
    }
    try {
      const response = await fetch(apiUrl("/api/professional/receivables/update"), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          patient_key: patientKey,
          action,
          received_cents: receivedCents,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Falha ao atualizar recebimento.");
      setMessage("Recebimento atualizado.");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Falha ao atualizar recebimento.");
    }
  };

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">
            Administrativo
          </p>
          <h2 className="mt-1 text-sm font-bold text-slate-100">Recebimentos por paciente</h2>
        </div>
        <div className="grid grid-cols-3 gap-2 text-right text-[10px]">
          {[
            ["Devido", summary?.total_due_brl || "R$ 0,00", "text-cyan-200"],
            ["Recebido", summary?.total_received_brl || "R$ 0,00", "text-emerald-200"],
            ["Pendente", summary?.total_pending_brl || "R$ 0,00", "text-amber-100"],
          ].map(([label, value, tone]) => (
            <div key={label} className="rounded border border-slate-700 bg-slate-950 px-3 py-2">
              <p className="font-black uppercase text-slate-500">{label}</p>
              <p className={`mt-1 whitespace-nowrap font-black ${tone}`}>{value}</p>
            </div>
          ))}
        </div>
      </div>
      {message && <p className="mt-3 text-xs font-bold text-cyan-200">{message}</p>}
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-max table-auto text-left text-[10px]">
          <thead className="uppercase text-slate-500">
            <tr>
              {[
                "Paciente", "Sessões", "Pacotes", "Avulsas", "Devido", "Recebido",
                "Pendente", "Último convite", "Status", "Ações",
              ].map((label) => <th key={label} className="whitespace-nowrap px-2 py-2">{label}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {!loading && !rows.length && (
              <tr><td colSpan={10} className="px-2 py-4 text-slate-400">Nenhum recebimento registrado.</td></tr>
            )}
            {rows.map((row) => (
              <tr key={row.patient_key}>
                <td className="px-2 py-2">
                  <p className="font-black text-slate-100">{row.patient?.name || "Paciente sem nome"}</p>
                  <p className="text-[9px] text-slate-500">{row.patient?.email || row.patient?.phone || ""}</p>
                </td>
                <td className="px-2 py-2">{row.session_count}</td>
                <td className="px-2 py-2">{row.package_count}</td>
                <td className="px-2 py-2">{row.single_count}</td>
                <td className="px-2 py-2 font-bold text-cyan-200">{row.total_due_brl}</td>
                <td className="px-2 py-2 font-bold text-emerald-200">{row.total_received_brl}</td>
                <td className="px-2 py-2 font-bold text-amber-100">{row.total_pending_brl}</td>
                <td className="px-2 py-2 text-slate-400">{row.last_invite_at ? new Date(row.last_invite_at).toLocaleDateString("pt-BR") : "--"}</td>
                <td className="px-2 py-2">
                  <span className={`rounded border px-2 py-1 font-black uppercase ${statusStyle[row.status] || statusStyle.sem_valor}`}>
                    {row.status.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-2 py-2">
                  <div className="flex flex-nowrap gap-1">
                    <button type="button" onClick={() => void update(row.patient_key, "paid")} className="rounded border border-emerald-700 px-2 py-1 text-emerald-200">Recebido</button>
                    <button type="button" onClick={() => void update(row.patient_key, "partial")} className="rounded border border-amber-700 px-2 py-1 text-amber-100">Parcial</button>
                    <button type="button" onClick={() => void update(row.patient_key, "pending")} className="rounded border border-slate-700 px-2 py-1 text-slate-300">Pendente</button>
                    <button type="button" onClick={() => openReceipt(row)} className="rounded border border-cyan-700 px-2 py-1 text-cyan-200">Recibo</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
