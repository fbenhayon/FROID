import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AIInsights } from "../components/panels/AIInsights";
import { apiUrl } from "../lib/api";
import {
  formatDuration,
  loadSessionReport,
  MetricSnapshot,
  SessionReportRecord,
} from "../lib/session-report";

interface Props {
  user?: any;
}

const DEFAULT_SECTIONS = {
  baseline: true,
  averages: true,
  cuts: true,
  summaries: true,
  notes: true,
  dissonances: true,
  transcript: false,
};

type SectionKey = keyof typeof DEFAULT_SECTIONS;

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return Number(value).toFixed(digits);
}

function metricRows(snapshot: MetricSnapshot) {
  return [
    ["IPM", fmt(snapshot.ipmAvg, 1)],
    ["IDM", fmt(snapshot.idmAvg, 2)],
    ["Zona dominante", snapshot.dominantZone ? `Zona ${snapshot.dominantZone}` : "--"],
    ["Tema", snapshot.theme || "--"],
    ["Tom emocional", snapshot.emotionalTone || "--"],
    ["Palavras/min", fmt(snapshot.wordsPerMinute, 1)],
    ["Dissonancias", String(snapshot.dissonanceCount || 0)],
    ["MFCC7", fmt(snapshot.mfcc7, 3)],
    ["MFCC9", fmt(snapshot.mfcc9, 3)],
    ["F0 medio", fmt(snapshot.f0Mean, 2)],
    ["ZCR", fmt(snapshot.zcr, 3)],
    ["Jitter", fmt(snapshot.jitter, 3)],
    ["Shimmer", fmt(snapshot.shimmer, 3)],
    ["Sub-harmonico 5-12Hz", fmt(snapshot.subharmonic5_12, 3)],
    ["Sub-harmonico 12-20Hz", fmt(snapshot.subharmonic12_20, 3)],
  ];
}

const MetricList: React.FC<{ title: string; snapshot: MetricSnapshot }> = ({
  title,
  snapshot,
}) => (
  <section className="rounded-lg border border-slate-200 bg-white p-4">
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-sm font-bold text-slate-900">{title}</h2>
      <span className="rounded bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-500">
        {snapshot.label}
      </span>
    </div>
    <div className="grid gap-2 md:grid-cols-3">
      {metricRows(snapshot).map(([label, value]) => (
        <div key={label} className="rounded border border-slate-100 bg-slate-50 p-2">
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {label}
          </p>
          <p className="mt-0.5 text-sm font-semibold text-slate-800">{value}</p>
        </div>
      ))}
    </div>
  </section>
);

export const SessionReport: React.FC<Props> = () => {
  const { sessionId = "" } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<SessionReportRecord | null>(() =>
    loadSessionReport(sessionId) || null,
  );
  const [sections, setSections] = useState(DEFAULT_SECTIONS);

  useEffect(() => {
    let active = true;
    if (report || !sessionId) return;
    fetch(apiUrl(`/api/session-reports/${sessionId}`))
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (active && data?.sessionId) setReport(data);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [report, sessionId]);

  const reportContext = useMemo(() => {
    if (!report) return {};
    return {
      report_baseline: report.baseline,
      report_session_average: report.sessionAverage,
      report_ten_minute_cuts: report.tenMinuteCuts,
      report_notes_count: report.clinicalNotes.length,
      report_summaries: report.conversationSummaries,
    };
  }, [report]);

  if (!report) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6 text-slate-700">
        <div className="max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
          <h1 className="text-lg font-bold text-slate-900">
            Relatorio nao encontrado
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            O relatorio da sessao ainda nao foi gerado neste navegador.
          </p>
          <button
            onClick={() => navigate("/dashboard")}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700"
          >
            Voltar ao dashboard
          </button>
        </div>
      </div>
    );
  }

  const toggle = (key: SectionKey) =>
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-blue-600">
              Relatorio da Consulta
            </p>
            <h1 className="text-xl font-bold text-slate-900">
              Sessao {report.sessionId}
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              {new Date(report.createdAt).toLocaleString("pt-BR")} | Duracao{" "}
              {formatDuration(report.durationSeconds)}
            </p>
          </div>
          <button
            onClick={() => navigate("/dashboard")}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
          >
            Dashboard
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-4 p-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <section className="rounded-lg border border-blue-100 bg-blue-50 p-4">
            <h2 className="mb-3 text-sm font-bold text-blue-950">
              Linha comparativa da sessao
            </h2>
            <div className="grid gap-2 md:grid-cols-5">
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  IPM baseline
                </p>
                <p className="text-lg font-black text-blue-950">
                  {fmt(report.baseline.ipmAvg, 1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  IPM medio
                </p>
                <p className="text-lg font-black text-blue-950">
                  {fmt(report.sessionAverage.ipmAvg, 1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  IDM baseline
                </p>
                <p className="text-lg font-black text-blue-950">
                  {fmt(report.baseline.idmAvg, 2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  IDM medio
                </p>
                <p className="text-lg font-black text-blue-950">
                  {fmt(report.sessionAverage.idmAvg, 2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase text-blue-500">
                  Tema inicial
                </p>
                <p className="text-sm font-bold text-blue-950">
                  {report.baseline.theme}
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-bold text-slate-900">
              Composicao do relatorio
            </h2>
            <div className="grid gap-2 md:grid-cols-4">
              {(Object.keys(sections) as SectionKey[]).map((key) => (
                <label
                  key={key}
                  className="flex items-center gap-2 rounded border border-slate-100 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-600"
                >
                  <input
                    type="checkbox"
                    checked={sections[key]}
                    onChange={() => toggle(key)}
                  />
                  {key}
                </label>
              ))}
            </div>
          </section>

          {sections.baseline && (
            <MetricList title="Parametros iniciais - 60 segundos" snapshot={report.baseline} />
          )}
          {sections.averages && (
            <MetricList title="Media das metricas da sessao" snapshot={report.sessionAverage} />
          )}

          {sections.cuts && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                Cortes de 10 minutos
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="py-2">Corte</th>
                      <th>IPM</th>
                      <th>IDM</th>
                      <th>Zona</th>
                      <th>PPM</th>
                      <th>Tema</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {report.tenMinuteCuts.map((cut) => (
                      <tr key={cut.label}>
                        <td className="py-2 font-bold text-slate-700">{cut.label}</td>
                        <td>{fmt(cut.ipmAvg, 1)}</td>
                        <td>{fmt(cut.idmAvg, 2)}</td>
                        <td>{cut.dominantZone || "--"}</td>
                        <td>{fmt(cut.wordsPerMinute, 1)}</td>
                        <td>{cut.theme}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {sections.summaries && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                Temas e resumos por janela
              </h2>
              <div className="space-y-2">
                {report.conversationSummaries.map((item) => (
                  <div key={item.id} className="rounded border border-slate-100 bg-slate-50 p-3">
                    <p className="text-xs font-bold text-slate-800">
                      {item.startMinute}-{item.endMinute}min | {item.theme}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">
                      {item.summary}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.notes && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                Observacoes do profissional
              </h2>
              <div className="space-y-2">
                {report.clinicalNotes.length === 0 && (
                  <p className="text-xs italic text-slate-400">
                    Nenhuma anotacao clinica registrada.
                  </p>
                )}
                {report.clinicalNotes.map((note) => (
                  <div key={note.id} className="rounded border border-slate-100 bg-slate-50 p-3">
                    <p className="whitespace-pre-wrap text-xs text-slate-700">
                      {note.text}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-400">
                      {new Date(note.timestamp).toLocaleString("pt-BR")}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.dissonances && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                Dissonancias registradas
              </h2>
              <div className="space-y-2">
                {report.dissonances.length === 0 && (
                  <p className="text-xs italic text-slate-400">
                    Nenhuma dissonancia persistente registrada.
                  </p>
                )}
                {report.dissonances.map((item) => (
                  <div key={item.id} className="rounded border border-red-100 bg-red-50 p-3">
                    <p className="text-xs font-bold text-red-900">
                      Zona {item.zone} | {item.elapsedSeconds}s
                    </p>
                    <p className="mt-1 text-xs text-red-800">{item.report}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {sections.transcript && (
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-bold text-slate-900">
                Transcricao da sessao
              </h2>
              <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded bg-slate-950 p-3 text-xs leading-relaxed text-slate-100">
                {report.transcript || "Sem transcricao arquivada."}
              </pre>
            </section>
          )}
        </div>

        <aside className="min-h-[520px] rounded-lg border border-slate-200 bg-white p-4">
          <AIInsights
            zones={report.sessionAverage.zones || []}
            ipmScore={report.sessionAverage.ipmAvg}
            coherenceStatus={report.sessionAverage.coherenceStatus}
            baselineEstablished
            sessionId={report.sessionId}
            extraContext={reportContext}
          />
        </aside>
      </main>
    </div>
  );
};
