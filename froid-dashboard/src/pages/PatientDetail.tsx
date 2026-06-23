import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AIInsights } from "../components/panels/AIInsights";
import { apiUrl } from "../lib/api";
import {
  buildPatientGroups,
  formatDateTime,
  limitWords,
  mergeReports,
  reportEndDate,
  reportStartDate,
  shortId,
} from "../lib/patient-dashboard";
import {
  formatDuration,
  loadSessionReports,
  SessionReportRecord,
} from "../lib/session-report";

export const PatientDetail: React.FC = () => {
  const navigate = useNavigate();
  const { patientKey = "" } = useParams<{ patientKey: string }>();
  const decodedPatientKey = decodeURIComponent(patientKey);
  const [reports, setReports] = useState<SessionReportRecord[]>(() =>
    loadSessionReports(),
  );

  useEffect(() => {
    let active = true;
    fetch(apiUrl("/api/session-reports"))
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!active) return;
        const remoteReports: SessionReportRecord[] = Array.isArray(data?.reports)
          ? data.reports
          : Array.isArray(data)
            ? data
            : [];
        if (remoteReports.length) {
          setReports((current) => mergeReports(current, remoteReports));
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const group = useMemo(
    () => buildPatientGroups(reports).find((item) => item.key === decodedPatientKey),
    [decodedPatientKey, reports],
  );

  if (!group) {
    return (
      <div className="min-h-screen bg-white p-1 text-black">
        <button
          onClick={() => navigate("/dashboard")}
          className="border border-black px-2 py-0.5 text-[10px]"
        >
          Voltar ao Dashboard
        </button>
        <h1 className="mt-5 text-xl font-bold">Paciente nao encontrado</h1>
        <p className="mt-2 text-xs">
          Ainda nao ha relatorios locais ou sincronizados para este paciente.
        </p>
      </div>
    );
  }

  const latest = group.latestReport;
  const context = {
    patient: group.patient,
    patient_summary: {
      total_sessions: group.totalSessions,
      completed_sessions: group.completedSessions,
      active_sessions: group.activeSessions,
      total_analyses: group.totalAnalyses,
      dominant_zone: group.dominantZone,
      recurrent_emotion: group.recurrentEmotion,
      clinical_risk: group.clinicalRisk,
      clinical_note: group.clinicalNote,
    },
    latest_report_baseline: latest.baseline,
    latest_report_average: latest.sessionAverage,
    latest_report_cuts: latest.tenMinuteCuts,
  };

  return (
    <div className="min-h-screen bg-white p-1 text-black">
      <button
        onClick={() => navigate("/dashboard")}
        className="border border-black px-2 py-0.5 text-[10px]"
      >
        Voltar ao Dashboard
      </button>

      <h1 className="mt-4 text-2xl font-bold">
        {group.patient.name || "Paciente sem nome"}
      </h1>
      <p className="mt-4 text-xs">
        CPF: {group.patient.document || "Nao informado"}
      </p>

      <section className="mt-8 grid grid-cols-4 gap-4 text-xs">
        <Counter label="Total de Sessoes" value={group.totalSessions} />
        <Counter label="Sessoes Concluidas" value={group.completedSessions} />
        <Counter label="Sessoes Ativas" value={group.activeSessions} />
        <Counter label="Total de Analises" value={group.totalAnalyses} />
      </section>

      <section className="mt-7">
        <h2 className="text-lg font-bold">Indicadores Clinicos</h2>
        <div className="mt-6 grid grid-cols-3 gap-10 text-xs">
          <Indicator
            label="Zona FROID Dominante"
            value={group.dominantZone ? `Zona ${group.dominantZone}` : "--"}
            detail={`Baseado em ${group.completedSessions} sessoes`}
          />
          <Indicator
            label="Emocao Recorrente"
            value={group.recurrentEmotion || "--"}
            detail="FACS - Analise Facial"
          />
          <Indicator
            label="Risco Clinico"
            value={group.clinicalRisk}
            detail={group.riskTypes}
          />
        </div>
        <p className="mt-5 text-xs">
          <strong>Nota Clinica:</strong> {group.clinicalNote}
        </p>
      </section>

      <section className="mt-5">
        <h2 className="text-lg font-bold">Historico de Sessoes</h2>
        <table className="mt-3 w-full table-fixed text-left text-xs">
          <thead>
            <tr className="font-bold">
              <th className="w-[13%]">ID</th>
              <th className="w-[12%]">STATUS</th>
              <th className="w-[23%]">INICIO</th>
              <th className="w-[23%]">FIM</th>
              <th className="w-[17%]">DURACAO</th>
              <th>ANALISES</th>
            </tr>
          </thead>
          <tbody>
            {group.reports.map((report, index) => (
              <tr key={report.sessionId}>
                <td>
                  <button
                    onClick={() => navigate(`/session/${report.sessionId}/report`)}
                    className="underline-offset-2 hover:underline"
                  >
                    {shortId(report.sessionId)}
                  </button>
                </td>
                <td>{index === 0 ? "Concluida" : "Ativa"}</td>
                <td>{formatDateTime(reportStartDate(report))}</td>
                <td>{formatDateTime(reportEndDate(report))}</td>
                <td>{formatDuration(report.durationSeconds)}</td>
                <td>
                  {report.metricsAnalysis?.dashboard.populated_windows ||
                    report.tenMinuteCuts.filter((cut) => cut.sampleCount > 0)
                      .length}{" "}
                  registros
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-6 border border-black p-2">
        <h2 className="text-sm font-bold">Leitura das 3 ultimas sessoes</h2>
        <div className="mt-2 space-y-1 text-xs">
          {group.reports.slice(0, 3).map((report) => (
            <div key={report.sessionId}>
              {shortId(report.sessionId)} | IPM {report.baseline.ipmAvg.toFixed(1)} -{" "}
              {report.sessionAverage.ipmAvg.toFixed(1)} | IDM{" "}
              {report.baseline.idmAvg.toFixed(2)} -{" "}
              {report.sessionAverage.idmAvg.toFixed(2)} | Zona{" "}
              {report.sessionAverage.dominantZone || "--"} | Tema{" "}
              {limitWords(report.sessionAverage.theme || report.baseline.theme, 4)}
            </div>
          ))}
        </div>
      </section>

      <section className="mt-6 border border-black p-2">
        <AIInsights
          zones={latest.sessionAverage.zones || []}
          ipmScore={latest.sessionAverage.ipmAvg}
          coherenceStatus={latest.sessionAverage.coherenceStatus}
          baselineEstablished
          sessionId={latest.sessionId}
          extraContext={context}
        />
      </section>
    </div>
  );
};

const Counter: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <div>
    <p className="font-bold">{label}</p>
    <p className="mt-3">{value}</p>
  </div>
);

const Indicator: React.FC<{
  label: string;
  value: string;
  detail: string;
}> = ({ label, value, detail }) => (
  <div>
    <p className="font-bold">{label}</p>
    <p className="mt-5">{value}</p>
    <p className="mt-5 font-bold">{detail}</p>
  </div>
);
