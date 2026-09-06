import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { WaitingPatientSessions } from "../components/WaitingPatientSessions";
import { AIInsights } from "../components/panels/AIInsights";
import { FroidTooltip } from "../components/ui/FroidTooltip";
import { tooltipText } from "../lib/tooltip-i18n";
import { apiUrl } from "../lib/api";
import {
  buildPatientGroups,
  fmt,
  fmtDelta,
  formatDateTime,
  matchesPatientSearch,
  mergeReports,
  patientAdvancedSignal,
  paymentStatusForReport,
  professionalPortfolioSummary,
  reportEndDate,
  sessionMetricCells,
  sessionResultText,
  shortId,
} from "../lib/patient-dashboard";
import {
  loadSessionReports,
  MetricSnapshot,
  rememberSessionPatient,
  SessionReportRecord,
} from "../lib/session-report";
import {
  dashboardText,
  loadSessionLanguagePreferences,
  saveSessionLanguagePreferences,
  sessionLocaleOptions,
  type SessionLocale,
} from "../lib/localization";

interface DashboardProps {
  user?: any;
  onLogout?: () => void;
}

interface SessionEvent {
  id: number;
  type: "invite_created" | "invite_opened" | "invite_accepted" | "patient_joined";
  session_id: string;
  patient_name?: string;
  created_at: string;
}

interface ReceivableRow {
  patient_key: string;
  patient: {
    id?: string;
    name?: string;
    email?: string;
    phone?: string;
    document?: string;
  };
  total_due_cents: number;
  total_received_cents: number;
  total_pending_cents: number;
  total_due_brl: string;
  total_received_brl: string;
  total_pending_brl: string;
  session_count: number;
  package_count: number;
  single_count: number;
  last_invite_at: string;
  status: "recebido" | "parcial" | "pendente" | "sem_valor";
}

interface ReceivablesSummary {
  patients: number;
  total_due_brl: string;
  total_received_brl: string;
  total_pending_brl: string;
}

interface ProfessionalProfile {
  account_type?: "individual" | "organization";
  owner_name?: string;
  owner_email?: string;
  document?: string;
  phone?: string;
  organization_name?: string;
  organization_document?: string;
  profile_fields?: Record<string, string>;
  total_sessions?: number;
  used_sessions?: number;
  remaining_sessions?: number;
}

function makeId() {
  return `froid-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

const PRIORITY_STYLES: Record<string, string> = {
  ROTINA: "border-emerald-700 bg-emerald-950/40 text-emerald-200",
  OBSERVAR: "border-amber-600 bg-amber-950/40 text-amber-100",
  REVISAR: "border-orange-600 bg-orange-950/45 text-orange-100",
  "ALTA PRIORIDADE": "border-red-700 bg-red-950/55 text-red-100",
  "DADOS INSUFICIENTES": "border-slate-700 bg-slate-900 text-slate-300",
};

const SIGNAL_TOOLTIPS: Record<string, string> = {
  Atenção:
    "Prioridade atual do paciente na carteira. Sobe quando há maior ativação, risco, baixa estabilidade ou necessidade de revisão.",
  Carga:
    "Esforço clínico estimado a partir da intensidade multimodal, dissonâncias, risco agregado e marcadores de tensão.",
  Comunicação:
    "Disponibilidade de conteúdo clínico interpretável: resumos, cortes, anotações e consistência semântica das sessões.",
  Continuidade:
    "Grau de sustentação do acompanhamento no tempo, considerando quantidade de sessões e comparabilidade longitudinal.",
  Insight:
    "Índice de material analítico disponível para apoiar hipóteses clínicas, FROID Explica e revisão entre sessões.",
};

const METRIC_TOOLTIPS: Record<string, string> = {
  ipm: "IPM mede a intensidade global da energia emocional empregada na sessão.",
  idm: "IDM aponta direção e magnitude do desequilíbrio multimodal entre voz, face, zonas e baseline.",
  zone: "Zona FROID dominante observada no período analisado.",
  tone: "Tom emocional inferido a partir da composição vocal e semântica.",
  wpm: "Palavras por minuto, usado como indicador de cadência, aceleração, lentificação ou carga discursiva.",
  dissonance: "Quantidade de dissonâncias facial-vocais persistentes acima do limiar configurado.",
  mfcc7: "Biomarcador acústico acompanhado em contextos de valência negativa e risco depressivo quando combinado a outros sinais.",
  mfcc9: "Biomarcador acústico relevante para tensão autônoma e ansiedade somática em fala neutra/controlada.",
  f0: "Frequência fundamental média da voz, associada a variação de pitch e ativação.",
  zcr: "Taxa de cruzamento por zero, relacionada a textura acústica, ruído e dinâmica vocal.",
  jitter:
    "Índice proxy interno normalizado, derivado de ZCR escalado, útil para observar instabilidade vocal relativa. Não equivale diretamente a jitter percentual normativo.",
  shimmer:
    "Índice proxy interno normalizado da variação relativa do envelope RMS, útil para observar instabilidade de energia vocal. Não equivale diretamente a shimmer em dB.",
  sub5: "Energia sub-harmônica de 5-12 Hz, usada para rastrear tremores autonômicos da voz.",
  sub12: "Energia sub-harmônica de 12-20 Hz, complementar na leitura bioacústica e límbica.",
};

function scoreText(value: number) {
  return `${Math.round(value)}/100`;
}

function averageNumeric(values: Array<number | null | undefined>, fallback: number | null | undefined = 0) {
  const clean = values.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  if (!clean.length) return typeof fallback === "number" && Number.isFinite(fallback) ? fallback : 0;
  return clean.reduce((sum, value) => sum + value, 0) / clean.length;
}

function patientAverageSnapshot(reports: SessionReportRecord[]): MetricSnapshot {
  const snapshots = reports.map((report) => report.sessionAverage);
  const latest = snapshots[0] || ({} as MetricSnapshot);
  const zoneCounts = new Map<number, number>();
  snapshots.forEach((snapshot) => {
    if (snapshot.dominantZone) {
      zoneCounts.set(snapshot.dominantZone, (zoneCounts.get(snapshot.dominantZone) || 0) + 1);
    }
  });
  const dominantZone =
    [...zoneCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || latest.dominantZone || null;
  return {
    ...latest,
    label: "Média geral",
    ipmAvg: averageNumeric(snapshots.map((snapshot) => snapshot.ipmAvg), latest.ipmAvg),
    idmAvg: averageNumeric(snapshots.map((snapshot) => snapshot.idmAvg), latest.idmAvg),
    dominantZone,
    wordsPerMinute: averageNumeric(snapshots.map((snapshot) => snapshot.wordsPerMinute), latest.wordsPerMinute),
    dissonanceCount: Math.round(averageNumeric(snapshots.map((snapshot) => snapshot.dissonanceCount), latest.dissonanceCount || 0)),
    mfcc7: averageNumeric(snapshots.map((snapshot) => snapshot.mfcc7), latest.mfcc7),
    mfcc9: averageNumeric(snapshots.map((snapshot) => snapshot.mfcc9), latest.mfcc9),
    mfcc7Delta: averageNumeric(snapshots.map((snapshot) => snapshot.mfcc7Delta), latest.mfcc7Delta),
    mfcc9Delta: averageNumeric(snapshots.map((snapshot) => snapshot.mfcc9Delta), latest.mfcc9Delta),
    mfcc7DeltaDelta: averageNumeric(snapshots.map((snapshot) => snapshot.mfcc7DeltaDelta), latest.mfcc7DeltaDelta),
    mfcc9DeltaDelta: averageNumeric(snapshots.map((snapshot) => snapshot.mfcc9DeltaDelta), latest.mfcc9DeltaDelta),
    f0Mean: averageNumeric(snapshots.map((snapshot) => snapshot.f0Mean), latest.f0Mean),
    zcr: averageNumeric(snapshots.map((snapshot) => snapshot.zcr), latest.zcr),
    jitter: averageNumeric(snapshots.map((snapshot) => snapshot.jitter), latest.jitter),
    shimmer: averageNumeric(snapshots.map((snapshot) => snapshot.shimmer), latest.shimmer),
    spectralDelta0_4: averageNumeric(snapshots.map((snapshot) => snapshot.spectralDelta0_4), latest.spectralDelta0_4),
    spectralTheta4_8: averageNumeric(snapshots.map((snapshot) => snapshot.spectralTheta4_8), latest.spectralTheta4_8),
    spectralAlpha8_12: averageNumeric(snapshots.map((snapshot) => snapshot.spectralAlpha8_12), latest.spectralAlpha8_12),
    spectralBeta12_30: averageNumeric(snapshots.map((snapshot) => snapshot.spectralBeta12_30), latest.spectralBeta12_30),
    spectralGamma30_80: averageNumeric(snapshots.map((snapshot) => snapshot.spectralGamma30_80), latest.spectralGamma30_80),
    spectralBandIndex: averageNumeric(snapshots.map((snapshot) => snapshot.spectralBandIndex), latest.spectralBandIndex),
    subharmonic5_12: averageNumeric(
      snapshots.map((snapshot) => snapshot.subharmonic5_12),
      latest.subharmonic5_12,
    ),
    subharmonic12_20: averageNumeric(
      snapshots.map((snapshot) => snapshot.subharmonic12_20),
      latest.subharmonic12_20,
    ),
  };
}

function compactMetricCells(snapshot: MetricSnapshot) {
  return sessionMetricCells(snapshot).filter((cell) => cell.key !== "theme");
}

const ScoreBar: React.FC<{ label: string; value: number; color: string; locale: SessionLocale }> = ({
  label,
  value,
  color,
  locale,
}) => (
  <div>
    <div className="mb-1 flex items-center justify-between gap-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">
      <FroidTooltip
        width={320}
        content={
          <div>
            <p className="font-bold text-slate-900">{label}</p>
            <p className="mt-1">{tooltipText(locale, SIGNAL_TOOLTIPS[label] || "Indicador médio da carteira do paciente.")}</p>
          </div>
        }
      >
        <span className="cursor-help border-b border-dashed border-slate-500">
          {label}
        </span>
      </FroidTooltip>
      <span>{scoreText(value)}</span>
    </div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-800">
      <div
        className="h-full rounded-full"
        style={{ width: `${Math.max(4, Math.min(100, value))}%`, backgroundColor: color }}
      />
    </div>
  </div>
);

export const Dashboard: React.FC<DashboardProps> = ({ user, onLogout }) => {
  const nav = useNavigate();
  const [patientActivity, setPatientActivity] = useState("");
  const [selectedPatientKey, setSelectedPatientKey] = useState("");
  const [patientSearch, setPatientSearch] = useState("");
  const [receivables, setReceivables] = useState<ReceivableRow[]>([]);
  const [receivablesSummary, setReceivablesSummary] = useState<ReceivablesSummary | null>(null);
  const [professionalProfile, setProfessionalProfile] = useState<ProfessionalProfile | null>(null);
  const [defaultSessionLocale, setDefaultSessionLocale] = useState<SessionLocale>(
    () => loadSessionLanguagePreferences().spokenLanguage,
  );
  const [reports, setReports] = useState<SessionReportRecord[]>(() =>
    loadSessionReports(),
  );
  const eventCursorRef = useRef<number | null>(null);
  const redirectingRef = useRef(false);
  const professionalName = user?.name || user?.email || "Profissional";
  // Só quem tem papel de gestão numa clínica REAL vê a área de gestão.
  //
  // No modo legado o backend sintetiza uma organização por profissional e lhe
  // atribui "owner" — o que faria o botão aparecer para todo autônomo, levando
  // a uma tela que só diz "não ativado". O próprio backend marca esses
  // contextos com legacy_fallback, então usamos isso para não oferecer uma
  // área que não existe para quem trabalha sozinho.
  const isClinicManager = useMemo(() => {
    const organizations = user?.organizations || [];
    const active =
      organizations.find(
        (organization: any) =>
          organization.organization_id === user?.active_organization_id,
      ) || organizations[0];
    if (!active || (active as any).legacy_fallback) return false;
    return (active.roles || []).some((role: string) =>
      ["owner", "administrator", "supervisor"].includes(String(role).toLowerCase()),
    );
  }, [user]);
  // A empresa contratante do NR-1 cai aqui depois do cadastro e nao tinha como
  // chegar ao proprio produto: nenhuma tela do painel apontava para /nr1, e a
  // rota so era alcancavel digitando a URL. O painel clinico e a casa errada
  // para ela, mas redirecionar seria pior — o painel NR-1 nao tem sair nem
  // administrativo, e ela ficaria sem saida.
  const isEmpresaNr1 =
    String(user?.access_status?.account_type || "") === "nr1_company";
  const tr = (text: string) => dashboardText(defaultSessionLocale, text);

  const updateDefaultSessionLocale = (locale: SessionLocale) => {
    setDefaultSessionLocale(locale);
    saveSessionLanguagePreferences({
      patientUiLocale: locale,
      spokenLanguage: locale,
      analysisLanguage: locale,
      reportLocale: locale,
    });
  };

  const authHeaders = (): Record<string, string> => {
    const token = localStorage.getItem("froid_token") || "";
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const loadReceivables = async () => {
    try {
      const response = await fetch(apiUrl("/api/professional/receivables"), {
        headers: authHeaders(),
      });
      const data = response.ok ? await response.json() : null;
      setReceivables(Array.isArray(data?.rows) ? data.rows : []);
      setReceivablesSummary(data?.summary || null);
    } catch {
      setReceivables([]);
      setReceivablesSummary(null);
    }
  };

  const loadProfessionalProfile = async () => {
    try {
      const response = await fetch(apiUrl("/api/professional/profile"), {
        headers: authHeaders(),
      });
      const data = response.ok ? await response.json() : null;
      setProfessionalProfile(data?.profile || null);
    } catch {
      setProfessionalProfile(null);
    }
  };

  useEffect(() => {
    setReports(loadSessionReports());
    void loadReceivables();
    void loadProfessionalProfile();
    let active = true;
    const token = localStorage.getItem("froid_token") || "";
    fetch(apiUrl("/api/session-reports"), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
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

  const patientGroups = useMemo(() => buildPatientGroups(reports), [reports]);
  const visiblePatientGroups = useMemo(
    () => patientGroups.filter((group) => matchesPatientSearch(group, patientSearch)),
    [patientGroups, patientSearch],
  );
  const portfolio = useMemo(
    () => professionalPortfolioSummary(patientGroups),
    [patientGroups],
  );
  const selectedGroup =
    patientGroups.find((group) => group.key === selectedPatientKey) ||
    patientGroups[0];
  const froidExplicaOperationalContext = useMemo(() => {
    const selectedSignal = selectedGroup
      ? patientAdvancedSignal(selectedGroup)
      : null;
    return {
      operational_scope: "professional_dashboard",
      patients_count: portfolio.totalPatients,
      active_patients_count: patientGroups.length,
      review_patients_count: portfolio.reviewCount,
      financial_summary: receivablesSummary,
      receivables_by_patient: receivables.slice(0, 80).map((row) => ({
        patient_key: row.patient_key,
        patient_name: row.patient?.name || "Paciente sem nome",
        total_due: row.total_due_brl,
        total_received: row.total_received_brl,
        total_pending: row.total_pending_brl,
        status: row.status,
        session_count: row.session_count,
        package_count: row.package_count,
        single_count: row.single_count,
      })),
      patients_summary: patientGroups.slice(0, 50).map((group) => {
        const signal = patientAdvancedSignal(group);
        return {
          patient_key: group.key,
          patient_name: group.patient.name || "Paciente sem nome",
          total_sessions: group.totalSessions,
          completed_sessions: group.completedSessions,
          active_sessions: group.activeSessions,
          latest_session_id: group.latestReport.sessionId,
          latest_session_at: group.latestReport.createdAt,
          priority: signal.priority,
          state: signal.state,
          action: signal.action,
          attention_index: Number(signal.attentionIndex.toFixed(1)),
          signal_load: Number(signal.signalLoad.toFixed(1)),
          communication: Number(signal.communication.toFixed(1)),
          continuity: Number(signal.continuity.toFixed(1)),
          insight: Number(signal.insight.toFixed(1)),
          dominant_zone: group.dominantZone,
          recurrent_emotion: group.recurrentEmotion,
          dissonance_events: group.dissonanceCount,
        };
      }),
      selected_patient: selectedGroup
        ? {
            patient_key: selectedGroup.key,
            patient_name: selectedGroup.patient.name || "Paciente sem nome",
            total_sessions: selectedGroup.totalSessions,
            completed_sessions: selectedGroup.completedSessions,
            active_sessions: selectedGroup.activeSessions,
            latest_session_id: selectedGroup.latestReport.sessionId,
            latest_session_at: selectedGroup.latestReport.createdAt,
            priority: selectedSignal?.priority,
            state: selectedSignal?.state,
            action: selectedSignal?.action,
            attention_index: selectedSignal
              ? Number(selectedSignal.attentionIndex.toFixed(1))
              : null,
            signal_load: selectedSignal
              ? Number(selectedSignal.signalLoad.toFixed(1))
              : null,
            communication: selectedSignal
              ? Number(selectedSignal.communication.toFixed(1))
              : null,
            continuity: selectedSignal
              ? Number(selectedSignal.continuity.toFixed(1))
              : null,
            insight: selectedSignal
              ? Number(selectedSignal.insight.toFixed(1))
              : null,
            dominant_zone: selectedGroup.dominantZone,
            recurrent_emotion: selectedGroup.recurrentEmotion,
            dissonance_events: selectedGroup.dissonanceCount,
          }
        : null,
    };
  }, [patientGroups, portfolio, receivables, receivablesSummary, selectedGroup]);
  const openPatientRegistration = (
    patient?: {
      name?: string;
      email?: string;
      phone?: string;
    },
    patientKey?: string,
    captureMode?: "patient_mobile",
  ) => {
    if (patientKey) setSelectedPatientKey(patientKey);
    const params = new URLSearchParams();
    if (patient?.name) params.set("name", patient.name);
    if (patient?.email) params.set("email", patient.email);
    if (patient?.phone) params.set("phone", patient.phone);
    if (captureMode) params.set("capture", captureMode);
    const query = params.toString();
    nav(`/patients/new${query ? `?${query}` : ""}`);
  };

  const startPresentialSession = (group = selectedGroup) => {
    const sessionId = makeId();
    const languages = loadSessionLanguagePreferences();
    if (group?.patient) {
      rememberSessionPatient(sessionId, {
        id: group.patient.id,
        name: group.patient.name,
        email: group.patient.email,
        phone: group.patient.phone,
        document: group.patient.document,
        sessionMode: "presential",
        captureProfile: "patient_external_media",
        ...languages,
      });
      setSelectedPatientKey(group.key);
    } else {
      rememberSessionPatient(sessionId, {
        name: "Paciente presencial",
        sessionMode: "presential",
        captureProfile: "patient_external_media",
        ...languages,
      });
    }
    nav(`/session/${sessionId}`);
  };

  const startPresentialMobileSession = (group = selectedGroup) => {
    openPatientRegistration(
      group?.patient
        ? {
            name: group.patient.name,
            email: group.patient.email,
            phone: group.patient.phone,
          }
        : undefined,
      group?.key,
      "patient_mobile",
    );
  };

  useEffect(() => {
    let active = true;

    const pollSessionEvents = async () => {
      try {
        if (eventCursorRef.current === null) {
          const response = await fetch(apiUrl("/api/session-events/latest"), {
            headers: authHeaders(),
          });
          if (!response.ok) return;
          const data = await response.json();
          eventCursorRef.current = Number(data?.latest_id || 0);
          return;
        }

        const response = await fetch(
          apiUrl(`/api/session-events?after=${eventCursorRef.current}`),
          { headers: authHeaders() },
        );
        if (!response.ok) return;
        const data = await response.json();
        const events: SessionEvent[] = Array.isArray(data?.events)
          ? data.events
          : [];
        eventCursorRef.current = Math.max(
          Number(eventCursorRef.current || 0),
          Number(data?.latest_id || 0),
          ...events.map((event) => Number(event.id || 0)),
        );
        const visibleEvents = events.filter((event) =>
          ["invite_opened", "invite_accepted", "patient_joined"].includes(
            event.type,
          ),
        );
        const latest = visibleEvents[visibleEvents.length - 1];
        if (!latest || !active) return;
        const patient = latest.patient_name || "Paciente";
        if (latest.type === "invite_opened") {
          setPatientActivity(`${patient} abriu o convite FROID.`);
        }
        if (latest.type === "invite_accepted") {
          setPatientActivity(`${patient} confirmou cadastro e consentimentos LGPD.`);
        }
        if (
          latest.type === "patient_joined" &&
          latest.session_id &&
          !redirectingRef.current
        ) {
          setPatientActivity(`${patient} entrou na sessão. Abrindo sala profissional...`);
          rememberSessionPatient(latest.session_id, { name: patient });
          redirectingRef.current = true;
          window.setTimeout(() => {
            if (active) nav(`/session/${latest.session_id}`);
          }, 900);
        }
      } catch {
        // Polling best-effort.
      }
    };

    void pollSessionEvents();
    const intervalId = window.setInterval(pollSessionEvents, 3000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [nav]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950 px-6 py-4">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">
              {tr("Dashboard Profissional")}
            </p>
            <h1 className="mt-1 text-xl font-bold text-slate-100">{professionalName}</h1>
          </div>
          <div className="w-full max-w-xs shrink-0 sm:w-64">
            <input
              type="search"
              value={patientSearch}
              onChange={(event) => setPatientSearch(event.target.value)}
              placeholder={tr("Buscar paciente...")}
              aria-label={tr("Buscar paciente")}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-100 placeholder:text-slate-500 focus:border-cyan-600 focus:outline-none"
            />
          </div>
          {/* Aqui havia um seletor de organização ativa.
              Retirado em 06/09/2026: escolher a empresa NR-1 nele não abria
              nada do NR-1 — esta tela é o painel clínico e continua sendo —
              e a troca estreitava as permissões da sessão (organization_type
              'enterprise' retira as permissões clínicas identificadas). O
              único efeito visível era os pacientes sumirem, sem explicação, e
              o mesmo seletor era a única forma de desfazer.

              A troca de contexto vive onde tem destino: em /admin, na lista
              "Clientes NR-1", que troca a organização E abre /nr1; e no botão
              "Dashboard" do painel NR-1, que faz o caminho de volta. */}
          <div className="flex flex-wrap items-center justify-end gap-2">
            {professionalProfile && (
              <span className="rounded-lg border border-emerald-800 bg-emerald-950 px-3 py-2 text-xs font-bold text-emerald-100">
                Saldo: {professionalProfile.remaining_sessions ?? "--"} sessões
              </span>
            )}
            {(user?.access_status?.admin || String(user?.email || "").toLowerCase() === "fbenhayon@gmail.com") && (
              <button
                onClick={() => nav("/admin")}
                className="rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100 hover:bg-cyan-900"
              >
                Admin
              </button>
            )}
            {isClinicManager && (
              <button
                onClick={() => nav("/clinica")}
                title={tr("Saldo compartilhado, uso por profissional, cotas e visibilidade dos relatórios da clínica.")}
                className="rounded-lg border border-emerald-800 bg-emerald-950 px-3 py-2 text-xs font-bold text-emerald-100 hover:bg-emerald-900"
              >
                {tr("Gestão da clínica")}
              </button>
            )}
            {isEmpresaNr1 && (
              <button
                onClick={() => nav("/nr1")}
                title="Painel de conformidade NR-1: campanhas, inventario de risco, AEP e eficacia das medidas."
                className="rounded-lg border border-amber-700 bg-amber-950 px-3 py-2 text-xs font-bold text-amber-100 hover:bg-amber-900"
              >
                Conformidade NR-1
              </button>
            )}
            {/* Mesmo defeito que o de cima, um passo antes: a empresa chegava
                ao painel NR-1 e nao tinha como voltar a cadastrar unidade. A
                rota /access/empresa nunca deixou de existir; o que faltava era
                alguem apontar para ela depois do cadastro concluido. */}
            {isEmpresaNr1 && (
              <button
                onClick={() => nav("/access/empresa")}
                title="Estabelecimentos e setores da empresa: acrescentar filial, criar setor, corrigir efetivo."
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
              >
                Estrutura da empresa
              </button>
            )}
            <button
              onClick={() => nav("/dashboard/resumido")}
              className="rounded-lg border border-violet-800 bg-violet-950 px-3 py-2 text-xs font-bold text-violet-100 hover:bg-violet-900"
            >
              {tr("Dashboard resumido")}
            </button>
            <button
              onClick={() => nav("/settings")}
              className="rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100 hover:bg-cyan-900"
            >
              {tr("Administrativo")}
            </button>
            <button
              onClick={onLogout}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
            >
              {tr("Sair")}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 p-6">

      <WaitingPatientSessions />

      {patientActivity && (
        <p className="rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100">
          {patientActivity}
        </p>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_460px]">
        <div className="contents">

          {/* FROID Explica fixo no topo (coluna única). */}
          <section className="sticky top-2 z-30 rounded-lg border border-cyan-900/70 bg-slate-900/95 p-3 shadow-lg shadow-slate-950/40 backdrop-blur xl:col-start-2 xl:row-span-3 xl:row-start-1 xl:self-start">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <h2 className="text-sm font-bold text-slate-100">FROID Explica</h2>
                <p className="mt-0.5 truncate text-[11px] text-slate-400">
                  {selectedGroup
                    ? tr("Contexto carregado a partir do paciente selecionado.")
                    : tr("Passe o mouse sobre um paciente para carregar o contexto.")}
                </p>
              </div>
              <button
                onClick={() => nav("/settings")}
                className="shrink-0 rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-1.5 text-[11px] font-bold text-cyan-100 hover:bg-cyan-900"
              >
                {tr("Meus prompts")}
              </button>
            </div>
            {selectedGroup ? (
              <div className="mt-2 max-h-72 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 px-2 pb-2 pr-1">
                <AIInsights
                  responseLocale={defaultSessionLocale}
                  zones={selectedGroup.latestReport.sessionAverage.zones || []}
                  ipmScore={selectedGroup.latestReport.sessionAverage.ipmAvg}
                  coherenceStatus={
                    selectedGroup.latestReport.sessionAverage.coherenceStatus
                  }
                  baselineEstablished
                  sessionId={selectedGroup.latestReport.sessionId}
                  extraContext={{
                    ...froidExplicaOperationalContext,
                    patient: selectedGroup.patient,
                    latest_report_average: selectedGroup.latestReport.sessionAverage,
                    latest_report_baseline: selectedGroup.latestReport.baseline,
                    last_three_sessions: selectedGroup.reports.slice(0, 3).map((report) => ({
                      session_id: report.sessionId,
                      average: report.sessionAverage,
                      result: sessionResultText(report, 120),
                      payment_status: paymentStatusForReport(report),
                    })),
                  }}
                  controlsSticky
                  rootClassName="border-0 bg-transparent text-slate-100"
                  messagesClassName="min-h-32 max-h-56 bg-slate-800/80 text-slate-200"
                />
              </div>
            ) : (
              <p className="mt-2 rounded-lg border border-slate-700 bg-slate-950 p-3 text-[11px] leading-relaxed text-slate-400">
                Selecione um paciente abaixo para habilitar perguntas ao FROID
                Explica com contexto clínico longitudinal.
              </p>
            )}
          </section>


      <section className="rounded-lg border border-slate-800 bg-slate-900 p-3 shadow-sm">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] leading-relaxed">
          <strong className="text-sm text-slate-100">{tr("Resumo profissional")}</strong>
          <span><b className="text-slate-500">{tr("Pacientes")}:</b> {portfolio.totalPatients}</span>
          <span><b className="text-slate-500">{tr("Devido")}:</b> <em className="not-italic text-cyan-200">{receivablesSummary?.total_due_brl || "R$ 0,00"}</em></span>
          <span><b className="text-slate-500">{tr("Recebido")}:</b> <em className="not-italic text-emerald-200">{receivablesSummary?.total_received_brl || "R$ 0,00"}</em></span>
          <span><b className="text-slate-500">{tr("Pendente")}:</b> <em className="not-italic text-amber-100">{receivablesSummary?.total_pending_brl || "R$ 0,00"}</em></span>
          <span><b className="text-slate-500">{tr("Carga")}:</b> {scoreText(portfolio.meanSignalLoad)}</span>
          <span><b className="text-slate-500">{tr("Comunicação")}:</b> {scoreText(portfolio.meanCommunication)}</span>
          <span><b className="text-slate-500">{tr("Continuidade")}:</b> {scoreText(portfolio.meanContinuity)}</span>
          <span><b className="text-slate-500">{tr("Para revisão")}:</b> {portfolio.reviewCount}</span>
        </div>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-slate-100">{tr("Meus Pacientes")}</h2>
          <p className="mt-1 text-[11px] text-slate-400">
            {tr("Incluir Paciente")}
          </p>
        </div>
        <div className="flex flex-nowrap justify-end gap-2 overflow-x-auto">
          <div
            role="radiogroup"
            aria-label={tr("Idioma")}
            className="flex shrink-0 items-center rounded-lg border border-slate-700 bg-slate-950 p-1"
          >
            <div className="flex items-center rounded-md border border-slate-800 bg-slate-900 p-0.5">
              {sessionLocaleOptions().map((option) => {
                const selected = option.value === defaultSessionLocale;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    aria-label={option.label}
                    title={`${option.label}${option.validationStatus === "pilot" ? " · validação controlada" : ""}`}
                    onClick={() => updateDefaultSessionLocale(option.value)}
                    className={`min-w-8 rounded px-2 py-1.5 text-[10px] font-black tracking-wide transition-colors ${
                      selected
                        ? "bg-cyan-700 text-white shadow-sm shadow-cyan-950"
                        : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                    }`}
                  >
                    {option.value.split("-")[0].toUpperCase()}
                  </button>
                );
              })}
            </div>
          </div>
          <button
            onClick={() => openPatientRegistration()}
            title={tr(
              "Paciente e profissional em locais diferentes. O paciente entra pelo celular ou computador, com áudio e vídeo funcionando nos dois sentidos, incluindo o botão \"Ouvir paciente\".",
            )}
            className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-800"
          >
            {tr("Sessão Remota")}
          </button>
          <button
            onClick={() => startPresentialSession()}
            title={tr(
              "Ambos juntos na mesma sala, usando só o dispositivo do profissional: a câmera e o microfone dele capturam o paciente diretamente, sem chamada nem áudio reproduzido.",
            )}
            className="rounded-lg border border-emerald-700 bg-emerald-950 px-3 py-2 text-xs font-bold text-emerald-100 hover:bg-emerald-900"
          >
            {tr("Presencial")}
          </button>
          <button
            onClick={() => startPresentialMobileSession()}
            title={tr(
              "Ambos juntos na mesma sala; o celular do paciente funciona como câmera dedicada e o áudio dele não é reproduzido (evita eco). Não use se o paciente estiver remoto.",
            )}
            className="rounded-lg border border-violet-700 bg-violet-950 px-3 py-2 text-xs font-bold text-violet-100 hover:bg-violet-900"
          >
            {tr("Presencial · Celular")}
          </button>
        </div>
        </div>
      </section>

      <section className="space-y-4">
        {visiblePatientGroups.length === 0 && (
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-xs text-slate-400">
            {patientGroups.length === 0
              ? "Nenhum paciente com relatório encontrado. Finalize uma sessão para alimentar o dashboard profissional."
              : tr("Nenhum paciente encontrado para esta busca.")}
          </div>
        )}

        {visiblePatientGroups.map((group) => {
          const signal = patientAdvancedSignal(group);
          const averageSnapshot = patientAverageSnapshot(group.reports);
          const priorityClass =
            PRIORITY_STYLES[signal.priority] ||
            PRIORITY_STYLES["DADOS INSUFICIENTES"];
          return (
          <article
            key={group.key}
            className="rounded-lg border border-slate-800 bg-slate-900 p-4 shadow-sm"
            onMouseEnter={() => setSelectedPatientKey(group.key)}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-black uppercase tracking-wide text-slate-100">
                  {group.patient.name || tr("Paciente sem nome")}
                </h3>
                <p className="mt-1 text-xs text-slate-400">
                  ID: {group.patient.document || tr("Não informado")} - {group.totalSessions} {tr("Sessões").toLowerCase()}
                </p>
              </div>
              <div className="min-w-[320px] flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-[11px] text-slate-300">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span>
                    <strong>{tr("Ação sugerida")}:</strong> {signal.action}
                  </span>
                  <span>
                    <strong>{tr("Qualidade")}:</strong> {signal.qualityLabel}
                  </span>
                  <span>
                    <strong>{tr("Estado atual")}:</strong> {signal.state}
                  </span>
                </div>
              </div>
              <div className="flex h-fit flex-nowrap justify-end gap-2 overflow-x-auto whitespace-nowrap">
                <span
                  className={`rounded-full border px-2 py-1 text-[10px] font-black ${priorityClass}`}
                >
                  {signal.priority}
                </span>
                <button
                  onClick={() =>
                    openPatientRegistration(
                      {
                        name: group.patient.name,
                        email: group.patient.email,
                        phone: group.patient.phone,
                      },
                      group.key,
                    )
                  }
                  title={tr(
                    "Paciente e profissional em locais diferentes. O paciente entra pelo celular ou computador, com áudio e vídeo funcionando nos dois sentidos, incluindo o botão \"Ouvir paciente\".",
                  )}
                  className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-800"
                >
                  {tr("Sessão Remota")}
                </button>
                <button
                  onClick={() => startPresentialSession(group)}
                  title={tr(
                    "Ambos juntos na mesma sala, usando só o dispositivo do profissional: a câmera e o microfone dele capturam o paciente diretamente, sem chamada nem áudio reproduzido.",
                  )}
                  className="rounded-lg border border-emerald-700 bg-emerald-950 px-3 py-2 text-xs font-bold text-emerald-100 hover:bg-emerald-900"
                >
                  {tr("Presencial")}
                </button>
                <button
                  onClick={() => startPresentialMobileSession(group)}
                  title={tr(
                    "Ambos juntos na mesma sala; o celular do paciente funciona como câmera dedicada e o áudio dele não é reproduzido (evita eco). Não use se o paciente estiver remoto.",
                  )}
                  className="rounded-lg border border-violet-700 bg-violet-950 px-3 py-2 text-xs font-bold text-violet-100 hover:bg-violet-900"
                >
                  {tr("Presencial · Celular")}
                </button>
                <button
                  onClick={() => {
                    setSelectedPatientKey(group.key);
                    nav(`/patients/${encodeURIComponent(group.key)}`, {
                      state: { returnTo: "/dashboard" },
                    });
                  }}
                  className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
                >
                  {tr("Ver Detalhes")}
                </button>
              </div>
            </div>

            <div className="mt-3 rounded-lg border border-slate-700 bg-slate-950 p-3">
              <p className="mb-2 text-xs font-black uppercase tracking-wide text-cyan-200">
                {tr("Indicadores médios de todas as sessões")}
              </p>
              <div className="grid gap-2 md:grid-cols-5">
                <ScoreBar label="Atenção" value={signal.attentionIndex} color="#ef4444" locale={defaultSessionLocale} />
                <ScoreBar label="Carga" value={signal.signalLoad} color="#f97316" locale={defaultSessionLocale} />
                <ScoreBar label="Comunicação" value={signal.communication} color="#0ea5e9" locale={defaultSessionLocale} />
                <ScoreBar label="Continuidade" value={signal.continuity} color="#22c55e" locale={defaultSessionLocale} />
                <ScoreBar label="Insight" value={signal.insight} color="#8b5cf6" locale={defaultSessionLocale} />
              </div>
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-max table-auto text-left text-[10px] leading-tight">
                  <thead className="text-[9px] uppercase tracking-normal text-slate-500">
                    <tr>
                      <th className="whitespace-nowrap py-1 pr-2">Corte</th>
                      {compactMetricCells(averageSnapshot).map((cell) => (
                        <th
                          key={`avg-head-${cell.key}`}
                          className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold"
                        >
                          <FroidTooltip
                            width={300}
                            content={
                              <div>
                                <p className="font-bold text-slate-900">{cell.label}</p>
                                <p className="mt-1">
                                  {tooltipText(defaultSessionLocale, METRIC_TOOLTIPS[cell.key] || "Métrica média consolidada das sessões do paciente.")}
                                </p>
                              </div>
                            }
                          >
                            <span className="cursor-help border-b border-dashed border-slate-500">
                              {cell.label}
                            </span>
                          </FroidTooltip>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    <tr className="align-top">
                      <td className="whitespace-nowrap py-1 pr-2 font-bold text-slate-300">
                        {tr("Média")}
                      </td>
                      {compactMetricCells(averageSnapshot).map((cell) => (
                        <td
                          key={`avg-value-${cell.key}`}
                          className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300"
                          title={cell.value}
                        >
                          {cell.value}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-3 min-w-0">
              <p className="text-xs font-black uppercase tracking-wide text-slate-100">
                {tr("Indicadores das últimas 3 sessões")}
              </p>
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-max table-auto text-left text-[10px] leading-tight">
                  <thead className="text-[9px] uppercase tracking-normal text-slate-500">
                    <tr>
                      <th className="whitespace-nowrap py-1 pr-2">Data / Pagamento / Detalhe</th>
                      {compactMetricCells(group.reports[0]?.sessionAverage || averageSnapshot).map((cell) => (
                        <th
                          key={`last-head-${cell.key}`}
                          className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold"
                        >
                          <FroidTooltip
                            width={300}
                            content={
                              <div>
                                <p className="font-bold text-slate-900">{cell.label}</p>
                                <p className="mt-1">
                                  {tooltipText(defaultSessionLocale, METRIC_TOOLTIPS[cell.key] || "Métrica desta sessão no acompanhamento do paciente.")}
                                </p>
                              </div>
                            }
                          >
                            <span className="cursor-help border-b border-dashed border-slate-500">
                              {cell.label}
                            </span>
                          </FroidTooltip>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {group.reports.slice(0, 3).map((report) => (
                      <tr key={report.sessionId} className="align-top">
                        <td className="whitespace-nowrap py-1 pr-2 text-slate-300">
                          <div className="flex items-center gap-2">
                            <span className="font-bold">{formatDateTime(reportEndDate(report))}</span>
                            <span className="rounded border border-slate-700 bg-slate-950 px-2 py-0.5 text-[9px] font-bold uppercase text-slate-300">
                              {paymentStatusForReport(report)}
                            </span>
                            <button
                              onClick={() => nav(`/session/${report.sessionId}/report`)}
                              className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] font-bold text-slate-200 hover:bg-slate-800"
                            >
                              {tr("Ver")}
                            </button>
                          </div>
                        </td>
                        {compactMetricCells(report.sessionAverage).map((cell) => (
                          <td
                            key={`${report.sessionId}-${cell.key}`}
                            className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300"
                            title={cell.value}
                          >
                            {cell.value}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-3 space-y-2">
                {group.reports.slice(0, 3).map((report) => (
                  <div
                    key={`result-${report.sessionId}`}
                    className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs leading-relaxed text-slate-300"
                  >
                    <strong className="text-cyan-200">
                      {tr("Resultado da sessão")} {shortId(report.sessionId)}:
                    </strong>{" "}
                    {sessionResultText(report, 85)}
                  </div>
                ))}
              </div>
            </div>
              <p className="mt-3 rounded border border-blue-800 bg-blue-950 px-3 py-2 text-[11px] font-medium text-blue-100">
                Linha comparativa mais recente: IPM{" "}
                {fmt(group.latestReport.baseline.ipmAvg, 1)} -&gt;{" "}
                {fmt(group.latestReport.sessionAverage.ipmAvg, 1)} (
                {fmtDelta(
                  group.latestReport.sessionAverage.ipmAvg -
                    group.latestReport.baseline.ipmAvg,
                  1,
                )}
                ) | IDM {fmt(group.latestReport.baseline.idmAvg, 2)} -&gt;{" "}
                {fmt(group.latestReport.sessionAverage.idmAvg, 2)}
              </p>
          </article>
          );
        })}
      </section>
        </div>
      </div>

      </main>
    </div>
  );
};
