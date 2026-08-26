import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import { GlossarioDeSiglas } from "../lib/siglas";

type AepSummary = {
  aep_id: string;
  unit_id: string | null;
  unit_name: string | null;
  status: string;
  reference_period: string;
  opened_at: string;
  concluded_at: string | null;
  method_count: number;
};

type Evidence = {
  evidence_id: string;
  method: string;
  collected_on: string;
  collected_by: string;
  summary: string;
  evidence_reference: string;
};

type Aep = {
  aep_id: string;
  unit_id: string;
  unit_name: string | null;
  status: string;
  reference_period: string;
  real_work_description: string;
  exposure: {
    duration: string;
    frequency: string;
    intensity: string;
    cofactors: string;
  };
  responsible_name: string;
  responsible_qualification: string;
  aet_required: boolean;
  aet_justification: string;
  preparation: {
    health_indicators: string;
    absenteeism_notes: string;
    previous_assessments: string;
  };
  opened_at: string;
  concluded_at: string | null;
  evidence: Evidence[];
  method_count: number;
  single_method_warning: boolean;
};

/** The methods the Guia MTE recognises for identifying psychosocial hazards. */
const METHODS: Array<{ value: string; label: string }> = [
  { value: "activity_observation", label: "Observação da atividade" },
  { value: "worker_dialogue", label: "Diálogo com o trabalhador" },
  { value: "questionnaire", label: "Pesquisa padronizada" },
  { value: "workshop", label: "Oficina" },
  { value: "focus_group", label: "Grupo focal" },
  { value: "document_analysis", label: "Análise documental" },
  { value: "cipa_manifestation", label: "Manifestação da CIPA (Comissão Interna de Prevenção de Acidentes e de Assédio)" },
];

const METHOD_LABEL = Object.fromEntries(
  METHODS.map((method) => [method.value, method.label]),
);

const STATUS_LABEL: Record<string, string> = {
  draft: "Rascunho",
  in_progress: "Em andamento",
  concluded: "Concluída",
  superseded: "Substituída",
};

/** Long-form fields, in the order the AEP is actually conducted. */
const TEXT_FIELDS: Array<{
  field: string;
  label: string;
  hint?: string;
  rows: number;
}> = [
  {
    field: "real_work_description",
    label: "Trabalho real",
    hint: "Como a atividade é de fato executada — não a tarefa prescrita no manual.",
    rows: 5,
  },
  {
    field: "exposure_duration",
    label: "Exposição — duração",
    rows: 2,
  },
  { field: "exposure_frequency", label: "Exposição — frequência", rows: 2 },
  { field: "exposure_intensity", label: "Exposição — intensidade", rows: 2 },
  {
    field: "exposure_cofactors",
    label: "Exposição — cofatores",
    hint: "Outros fatores que interferem na caracterização da exposição.",
    rows: 2,
  },
  {
    field: "health_indicators",
    label: "Preparação — indicadores de saúde",
    hint:
      "PCMSO (Programa de Controle Médico de Saúde Ocupacional), CAT " +
      "(Comunicação de Acidente de Trabalho), afastamentos considerados antes " +
      "de iniciar.",
    rows: 3,
  },
  { field: "absenteeism_notes", label: "Preparação — absenteísmo", rows: 2 },
  {
    field: "previous_assessments",
    label: "Preparação — avaliações anteriores",
    rows: 2,
  },
];

export const Nr1Aep: React.FC<{ user: FroidUser | null }> = ({ user }) => {
  const nav = useNavigate();
  const organizationId =
    user?.active_organization_id || user?.organizations?.[0]?.organization_id || "";
  const [items, setItems] = useState<AepSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [aep, setAep] = useState<Aep | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [aetRequired, setAetRequired] = useState(false);
  const [evidenceForm, setEvidenceForm] = useState({
    method: "activity_observation",
    collected_on: new Date().toISOString().slice(0, 10),
    collected_by: "",
    summary: "",
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

  const jsonHeaders = useMemo(
    () => ({ ...headers, "Content-Type": "application/json" }),
    [headers],
  );

  const loadList = useCallback(async () => {
    if (!organizationId) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/aep`),
        { headers },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível carregar as AEPs.");
      }
      setItems(Array.isArray(data.assessments) ? data.assessments : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar AEPs.");
    } finally {
      setLoading(false);
    }
  }, [headers, organizationId]);

  const loadAep = useCallback(
    async (aepId: string) => {
      if (!organizationId || !aepId) return;
      setLoading(true);
      setError("");
      try {
        const response = await fetch(
          apiUrl(`/api/organizations/${organizationId}/nr1/aep/${aepId}`),
          { headers },
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.detail || "Não foi possível abrir a AEP.");
        }
        const loaded = data as Aep;
        setAep(loaded);
        setForm({
          reference_period: loaded.reference_period || "",
          real_work_description: loaded.real_work_description || "",
          exposure_duration: loaded.exposure?.duration || "",
          exposure_frequency: loaded.exposure?.frequency || "",
          exposure_intensity: loaded.exposure?.intensity || "",
          exposure_cofactors: loaded.exposure?.cofactors || "",
          health_indicators: loaded.preparation?.health_indicators || "",
          absenteeism_notes: loaded.preparation?.absenteeism_notes || "",
          previous_assessments: loaded.preparation?.previous_assessments || "",
          responsible_name: loaded.responsible_name || "",
          responsible_qualification: loaded.responsible_qualification || "",
          aet_justification: loaded.aet_justification || "",
        });
        setAetRequired(Boolean(loaded.aet_required));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Falha ao abrir a AEP.");
      } finally {
        setLoading(false);
      }
    },
    [headers, organizationId],
  );

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const locked = aep?.status === "concluded" || aep?.status === "superseded";

  const save = async () => {
    if (!aep || locked) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/aep/${aep.aep_id}`),
        {
          method: "PATCH",
          headers: jsonHeaders,
          body: JSON.stringify({ ...form, aet_required: aetRequired }),
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível salvar.");
      setMessage("AEP salva.");
      await loadAep(aep.aep_id);
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar a AEP.");
    } finally {
      setLoading(false);
    }
  };

  const addEvidence = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!aep || locked) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(
          `/api/organizations/${organizationId}/nr1/aep/${aep.aep_id}/evidence`,
        ),
        { method: "POST", headers: jsonHeaders, body: JSON.stringify(evidenceForm) },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível registrar a evidência.");
      }
      setEvidenceForm((current) => ({ ...current, summary: "", collected_by: "" }));
      setMessage("Evidência registrada.");
      await loadAep(aep.aep_id);
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao registrar evidência.");
    } finally {
      setLoading(false);
    }
  };

  const conclude = async () => {
    if (!aep || locked) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        apiUrl(
          `/api/organizations/${organizationId}/nr1/aep/${aep.aep_id}/conclude`,
        ),
        { method: "POST", headers },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Não foi possível concluir.");
      setMessage("AEP concluída, datada e assinada.");
      await loadAep(aep.aep_id);
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao concluir a AEP.");
    } finally {
      setLoading(false);
    }
  };

  const canConclude =
    !!aep &&
    !locked &&
    Boolean(form.real_work_description?.trim()) &&
    Boolean(form.responsible_name?.trim()) &&
    (aep.evidence?.length || 0) > 0;

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <main className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
              NR-17 (Ergonomia) · Avaliação Ergonômica Preliminar
            </p>
            <h1 className="mt-2 text-2xl font-black text-white">
              Avaliação Ergonômica Preliminar (AEP) psicossocial
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">
              É o documento que a fiscalização pede primeiro, e é obrigatório
              para toda organização — inclusive as dispensadas do Programa de Gerenciamento de Riscos (PGR). Descreve o
              trabalho como ele é executado, não como está prescrito.
            </p>
          </div>
          <button
            onClick={() => nav("/nr1")}
            className="rounded border border-slate-700 px-4 py-2 text-xs font-black hover:bg-slate-900"
          >
            Voltar ao painel NR-1
          </button>
        </header>

        {error && (
          <p className="mt-4 rounded border border-red-900 bg-red-950 p-3 text-xs font-bold text-red-200">
            {error}
          </p>
        )}
        {message && (
          <p className="mt-4 rounded border border-emerald-900 bg-emerald-950 p-3 text-xs font-bold text-emerald-200">
            {message}
          </p>
        )}

        <div className="mt-5 grid gap-4 lg:grid-cols-[0.7fr_1.3fr]">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-black">Avaliações</h2>
              <button
                onClick={() => void loadList()}
                className="text-xs font-bold text-cyan-300"
              >
                Atualizar
              </button>
            </div>
            <div className="mt-3 space-y-2">
              {items.map((item) => (
                <button
                  key={item.aep_id}
                  type="button"
                  onClick={() => {
                    setSelectedId(item.aep_id);
                    setMessage("");
                    void loadAep(item.aep_id);
                  }}
                  className={`w-full rounded border p-3 text-left text-xs ${
                    selectedId === item.aep_id
                      ? "border-cyan-500 bg-cyan-950"
                      : "border-slate-700 bg-slate-950 hover:border-slate-500"
                  }`}
                >
                  <div className="flex justify-between gap-3">
                    <p className="font-black text-white">
                      {item.unit_name || "Unidade sem nome"}
                    </p>
                    <span className="uppercase text-cyan-200">
                      {STATUS_LABEL[item.status] || item.status}
                    </span>
                  </div>
                  <p className="mt-2 text-slate-400">
                    {item.reference_period || "Sem período"} ·{" "}
                    {item.method_count} método
                    {item.method_count === 1 ? "" : "s"}
                  </p>
                </button>
              ))}
              {!items.length && !loading && (
                <p className="rounded bg-slate-950 p-4 text-xs text-slate-400">
                  Nenhuma AEP aberta.
                </p>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            {!aep ? (
              <p className="text-sm text-slate-400">
                Selecione uma avaliação para conduzir.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-black text-white">
                      {aep.unit_name || "Unidade"} ·{" "}
                      {STATUS_LABEL[aep.status] || aep.status}
                    </h2>
                    {aep.concluded_at && (
                      <p className="mt-1 text-[11px] text-emerald-300">
                        Concluída em{" "}
                        {new Date(aep.concluded_at).toLocaleString("pt-BR")}
                      </p>
                    )}
                  </div>
                  {!locked && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => void save()}
                        disabled={loading}
                        className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 disabled:opacity-50"
                      >
                        Salvar
                      </button>
                      <button
                        onClick={() => void conclude()}
                        disabled={loading || !canConclude}
                        title={
                          canConclude
                            ? undefined
                            : "Exige trabalho real descrito, responsável nomeado e ao menos uma evidência"
                        }
                        className="rounded bg-cyan-600 px-4 py-2 text-xs font-black text-white disabled:opacity-40"
                      >
                        Concluir e assinar
                      </button>
                    </div>
                  )}
                </div>

                {aep.single_method_warning && (
                  <p className="mt-3 rounded border border-amber-900 bg-amber-950/50 p-3 text-[11px] leading-5 text-amber-100">
                    Esta AEP se apoia num único método. Questionário isolado não
                    comprova gestão de risco — combine com observação da
                    atividade ou diálogo com os trabalhadores.
                  </p>
                )}

                {locked && (
                  <p className="mt-3 rounded border border-slate-700 bg-slate-950 p-3 text-[11px] text-slate-400">
                    Documento concluído e datado. Para registrar mudanças, abra
                    uma nova avaliação da mesma unidade.
                  </p>
                )}

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <label className="block text-[10px] font-bold uppercase text-slate-400">
                    Período de referência
                    <input
                      value={form.reference_period || ""}
                      disabled={locked}
                      onChange={(event) =>
                        setForm((c) => ({ ...c, reference_period: event.target.value }))
                      }
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs normal-case text-white disabled:opacity-60"
                    />
                  </label>
                  <label className="block text-[10px] font-bold uppercase text-slate-400">
                    Responsável pela avaliação
                    <input
                      value={form.responsible_name || ""}
                      disabled={locked}
                      onChange={(event) =>
                        setForm((c) => ({ ...c, responsible_name: event.target.value }))
                      }
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs normal-case text-white disabled:opacity-60"
                    />
                  </label>
                  <label className="block text-[10px] font-bold uppercase text-slate-400 md:col-span-2">
                    Qualificação do responsável
                    <input
                      value={form.responsible_qualification || ""}
                      disabled={locked}
                      placeholder="A norma não exige profissão específica, mas exige conhecimento técnico adequado"
                      onChange={(event) =>
                        setForm((c) => ({
                          ...c,
                          responsible_qualification: event.target.value,
                        }))
                      }
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs normal-case text-white placeholder:text-slate-600 disabled:opacity-60"
                    />
                  </label>
                </div>

                {TEXT_FIELDS.map(({ field, label, hint, rows }) => (
                  <label
                    key={field}
                    className="mt-3 block text-[10px] font-bold uppercase text-slate-400"
                  >
                    {label}
                    {hint && (
                      <span className="ml-2 normal-case text-[10px] font-normal text-slate-500">
                        {hint}
                      </span>
                    )}
                    <textarea
                      value={form[field] || ""}
                      disabled={locked}
                      rows={rows}
                      onChange={(event) =>
                        setForm((c) => ({ ...c, [field]: event.target.value }))
                      }
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs normal-case leading-5 text-white disabled:opacity-60"
                    />
                  </label>
                ))}

                <div className="mt-4 rounded border border-slate-700 bg-slate-950 p-3">
                  <label className="flex items-center gap-2 text-xs font-bold text-slate-200">
                    <input
                      type="checkbox"
                      checked={aetRequired}
                      disabled={locked}
                      onChange={(event) => setAetRequired(event.target.checked)}
                    />
                    Exige AET — análise ergonômica aprofundada
                  </label>
                  {aetRequired && (
                    <textarea
                      value={form.aet_justification || ""}
                      disabled={locked}
                      rows={2}
                      placeholder="Justificativa do escalonamento"
                      onChange={(event) =>
                        setForm((c) => ({ ...c, aet_justification: event.target.value }))
                      }
                      className="mt-2 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white placeholder:text-slate-600 disabled:opacity-60"
                    />
                  )}
                </div>

                <h3 className="mt-6 text-sm font-black text-white">
                  Evidências ({aep.evidence.length}) · {aep.method_count} método
                  {aep.method_count === 1 ? "" : "s"}
                </h3>
                <div className="mt-2 space-y-2">
                  {aep.evidence.map((item) => (
                    <article
                      key={item.evidence_id}
                      className="rounded border border-slate-700 bg-slate-950 p-3 text-xs"
                    >
                      <div className="flex flex-wrap justify-between gap-2">
                        <p className="font-black text-cyan-200">
                          {METHOD_LABEL[item.method] || item.method}
                        </p>
                        <p className="text-slate-500">
                          {new Date(item.collected_on).toLocaleDateString("pt-BR")}
                          {item.collected_by ? ` · ${item.collected_by}` : ""}
                        </p>
                      </div>
                      <p className="mt-2 leading-5 text-slate-300">{item.summary}</p>
                    </article>
                  ))}
                  {!aep.evidence.length && (
                    <p className="rounded bg-slate-950 p-3 text-xs text-slate-400">
                      Nenhuma evidência registrada. A AEP não pode ser concluída
                      sem ao menos uma.
                    </p>
                  )}
                </div>

                {!locked && (
                  <form
                    onSubmit={addEvidence}
                    className="mt-4 rounded border border-slate-700 bg-slate-950 p-3"
                  >
                    <h4 className="text-xs font-black text-white">
                      Registrar evidência
                    </h4>
                    <div className="mt-2 grid gap-2 md:grid-cols-3">
                      <select
                        value={evidenceForm.method}
                        onChange={(event) =>
                          setEvidenceForm((c) => ({ ...c, method: event.target.value }))
                        }
                        className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                      >
                        {METHODS.map((method) => (
                          <option key={method.value} value={method.value}>
                            {method.label}
                          </option>
                        ))}
                      </select>
                      <input
                        type="date"
                        value={evidenceForm.collected_on}
                        onChange={(event) =>
                          setEvidenceForm((c) => ({
                            ...c,
                            collected_on: event.target.value,
                          }))
                        }
                        className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white"
                      />
                      <input
                        value={evidenceForm.collected_by}
                        placeholder="Quem coletou"
                        onChange={(event) =>
                          setEvidenceForm((c) => ({
                            ...c,
                            collected_by: event.target.value,
                          }))
                        }
                        className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white placeholder:text-slate-600"
                      />
                    </div>
                    <textarea
                      value={evidenceForm.summary}
                      rows={3}
                      placeholder="O que foi observado, dito ou apurado"
                      onChange={(event) =>
                        setEvidenceForm((c) => ({ ...c, summary: event.target.value }))
                      }
                      className="mt-2 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs leading-5 text-white placeholder:text-slate-600"
                    />
                    <button
                      type="submit"
                      disabled={loading || !evidenceForm.summary.trim()}
                      className="mt-2 rounded bg-cyan-600 px-4 py-2 text-xs font-black text-white disabled:opacity-40"
                    >
                      Registrar
                    </button>
                  </form>
                )}
              </>
            )}
          </section>
        </div>

        <GlossarioDeSiglas termos={["NR-1", "NR-17", "AEP", "AET", "PGR", "PCMSO", "CAT", "CIPA", "MTE"]} />
      </main>
    </div>
  );
};
