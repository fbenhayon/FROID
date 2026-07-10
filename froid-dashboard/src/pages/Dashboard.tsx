import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AIInsights } from "../components/panels/AIInsights";
import { FroidTooltip } from "../components/ui/FroidTooltip";
import { apiUrl } from "../lib/api";
import {
  buildPatientGroups,
  fmt,
  fmtDelta,
  formatDateTime,
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
  items?: ReceivableItem[];
}

interface ReceivableItem {
  invite_id?: string;
  session_id?: string;
  created_at?: string;
  accepted_at?: string;
  session_count?: number;
  payment_mode?: string;
  payment_status?: string;
  session_value_brl?: string;
  due_brl?: string;
  received_brl?: string;
  pending_brl?: string;
  received_at?: string;
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

const KPI_TOOLTIPS: Record<string, string> = {
  Pacientes:
    "Quantidade de pacientes com relatorios ou registros clinicos visiveis na carteira profissional.",
  "Atencao media":
    "Indice agregado de prioridade de acompanhamento. Combina sinais recentes, risco clinico, necessidade de revisao e intensidade multimodal.",
  "Carga clinica":
    "Carga multimodal media da carteira, considerando IPM, IDM, dissonancias, biomarcadores e qualidade/amostragem dos dados.",
  Comunicacao:
    "Qualidade documental e comunicacional: presenca de resumo, cortes, transcricao util, anotacoes e material suficiente para continuidade clinica.",
  Continuidade:
    "Consistencia longitudinal do acompanhamento: sessoes registradas, recorrencia de dados e disponibilidade de comparacao entre consultas.",
  "Para revisao":
    "Numero de pacientes que o FROID sinaliza para revisao por prioridade elevada, baixa qualidade de dados ou necessidade de acompanhamento profissional.",
};

const SIGNAL_TOOLTIPS: Record<string, string> = {
  Atencao:
    "Prioridade atual do paciente na carteira. Sobe quando ha maior ativacao, risco, baixa estabilidade ou necessidade de revisao.",
  Carga:
    "Esforco clinico estimado a partir da intensidade multimodal, dissonancias, risco agregado e marcadores de tensao.",
  Comunicacao:
    "Disponibilidade de conteudo clinico interpretavel: resumos, cortes, anotacoes e consistencia semantica das sessoes.",
  Continuidade:
    "Grau de sustentacao do acompanhamento no tempo, considerando quantidade de sessoes e comparabilidade longitudinal.",
  Insight:
    "Indice de material analitico disponivel para apoiar hipoteses clinicas, FROID Explica e revisao entre sessoes.",
};

const METRIC_TOOLTIPS: Record<string, string> = {
  ipm: "IPM mede a intensidade global da energia emocional empregada na sessao.",
  idm: "IDM aponta direcao e magnitude do desequilibrio multimodal entre voz, face, zonas e baseline.",
  zone: "Zona FROID dominante observada no periodo analisado.",
  tone: "Tom emocional inferido a partir da composicao vocal e semantica.",
  wpm: "Palavras por minuto, usado como indicador de cadencia, aceleração, lentificacao ou carga discursiva.",
  dissonance: "Quantidade de dissonancias facial-vocais persistentes acima do limiar configurado.",
  mfcc7: "Biomarcador acustico acompanhado em contextos de valencia negativa e risco depressivo quando combinado a outros sinais.",
  mfcc9: "Biomarcador acustico relevante para tensao autonoma e ansiedade somatica em fala neutra/controlada.",
  f0: "Frequencia fundamental media da voz, associada a variacao de pitch e ativacao.",
  zcr: "Taxa de cruzamento por zero, relacionada a textura acustica, ruido e dinamica vocal.",
  jitter:
    "Indice proxy interno normalizado, derivado de ZCR escalado, util para observar instabilidade vocal relativa. Nao equivale diretamente a jitter percentual normativo.",
  shimmer:
    "Indice proxy interno normalizado da variacao relativa do envelope RMS, util para observar instabilidade de energia vocal. Nao equivale diretamente a shimmer em dB.",
  sub5: "Energia sub-harmonica de 5-12 Hz, usada para rastrear tremores autonomicos da voz.",
  sub12: "Energia sub-harmonica de 12-20 Hz, complementar na leitura bioacustica e limbica.",
};

const RECEIVABLE_STATUS: Record<string, string> = {
  recebido: "border-emerald-700 bg-emerald-950/40 text-emerald-200",
  parcial: "border-amber-600 bg-amber-950/40 text-amber-100",
  pendente: "border-red-700 bg-red-950/50 text-red-100",
  sem_valor: "border-slate-700 bg-slate-900 text-slate-300",
};

function scoreText(value: number) {
  return `${Math.round(value)}/100`;
}

function escapeHtml(value: unknown) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function compactAddress(profile: ProfessionalProfile | null) {
  const fields = profile?.profile_fields || {};
  return [
    [fields.street, fields.number].filter(Boolean).join(", "),
    fields.complement,
    fields.district,
    [fields.city, fields.state].filter(Boolean).join(" - "),
    fields.postalCode ? `CEP ${fields.postalCode}` : "",
    fields.country,
  ]
    .filter(Boolean)
    .join(" | ");
}

function professionalReceiptInfo(profile: ProfessionalProfile | null, user?: any) {
  const fields = profile?.profile_fields || {};
  const isOrganization = profile?.account_type === "organization";
  const name = isOrganization
    ? fields.corporateName || profile?.organization_name || fields.tradeName || profile?.owner_name
    : fields.fullName || profile?.owner_name || user?.name;
  const document = isOrganization
    ? fields.cnpj || profile?.organization_document || profile?.document
    : fields.cpf || profile?.document;
  const contactEmail = isOrganization ? fields.companyEmail : fields.email;
  const contactPhone = isOrganization
    ? fields.companyMainPhone || fields.companyMobile || profile?.phone
    : fields.mobile || fields.phone || profile?.phone;
  return {
    name: name || user?.email || "Profissional FROID",
    tradeName: fields.tradeName || "",
    role: fields.profession || (isOrganization ? "Clinica/consultorio de saude" : "Profissional de saude"),
    document: document || "",
    registry: [fields.professionalCouncil, fields.professionalRegistry].filter(Boolean).join(" "),
    address: compactAddress(profile),
    email: contactEmail || profile?.owner_email || user?.email || "",
    phone: contactPhone || "",
    municipalRegistration: fields.municipalRegistration || "",
    stateRegistration: fields.stateRegistration || "",
    taxRegime: fields.taxRegime || "",
    receiptCity: fields.receiptCity || [fields.city, fields.state].filter(Boolean).join(" - "),
    serviceDescription:
      fields.receiptServiceDescription ||
      "Atendimento profissional em saude mental realizado com apoio operacional FROID.",
    fiscalObservation: fields.receiptFiscalObservation || "",
    isOrganization,
  };
}

function receiptDate(value?: string) {
  if (!value) return "--";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "--";
  return date.toLocaleDateString("pt-BR");
}

function openReceiptPrintWindow(
  row: ReceivableRow,
  profile: ProfessionalProfile | null,
  user?: any,
) {
  const info = professionalReceiptInfo(profile, user);
  const officialReference = window.prompt(
    "Referencia do recibo oficial Receita Saude/NFS-e, se houver:",
    "",
  ) || "";
  const payerName = window.prompt(
    "Nome do pagador, se diferente do paciente:",
    row.patient?.name || "",
  ) || row.patient?.name || "";
  const payerDocument = window.prompt(
    "CPF/CNPJ do pagador, se aplicavel:",
    row.patient?.document || "",
  ) || row.patient?.document || "";
  const issueDate = new Date();
  const internalId = row.items?.[0]?.session_id || row.patient_key;
  const items = row.items && row.items.length ? row.items : [];
  const rowsHtml = items.length
    ? items
        .map(
          (item) => `
            <tr>
              <td>${escapeHtml(item.session_id || item.invite_id || "--")}</td>
              <td>${escapeHtml(receiptDate(item.accepted_at || item.created_at))}</td>
              <td>${escapeHtml(item.session_count || 1)}</td>
              <td>${escapeHtml(item.session_value_brl || "--")}</td>
              <td>${escapeHtml(item.due_brl || "--")}</td>
              <td>${escapeHtml(item.received_brl || "--")}</td>
              <td>${escapeHtml(item.payment_status || row.status)}</td>
            </tr>
          `,
        )
        .join("")
    : `
      <tr>
        <td>${escapeHtml(internalId)}</td>
        <td>${escapeHtml(receiptDate(row.last_invite_at))}</td>
        <td>${escapeHtml(row.session_count)}</td>
        <td>--</td>
        <td>${escapeHtml(row.total_due_brl)}</td>
        <td>${escapeHtml(row.total_received_brl)}</td>
        <td>${escapeHtml(row.status)}</td>
      </tr>
    `;

  const html = `<!doctype html>
  <html lang="pt-BR">
    <head>
      <meta charset="utf-8" />
      <title>FROID - Fatura Recibo</title>
      <style>
        body { color: #0f172a; font-family: Arial, sans-serif; margin: 32px; }
        .top { border-bottom: 3px solid #0e7490; display: flex; justify-content: space-between; gap: 24px; padding-bottom: 14px; }
        .brand { color: #0e7490; font-size: 12px; font-weight: 900; letter-spacing: .25em; text-transform: uppercase; }
        h1 { font-size: 22px; margin: 8px 0 0; }
        h2 { border-bottom: 1px solid #cbd5e1; color: #334155; font-size: 13px; margin-top: 22px; padding-bottom: 6px; text-transform: uppercase; }
        .box { border: 1px solid #cbd5e1; border-radius: 8px; margin-top: 10px; padding: 12px; }
        .grid { display: grid; gap: 8px 16px; grid-template-columns: repeat(2, 1fr); }
        .label { color: #64748b; display: block; font-size: 10px; font-weight: 700; text-transform: uppercase; }
        .value { font-size: 13px; font-weight: 700; margin-top: 2px; }
        table { border-collapse: collapse; margin-top: 10px; width: 100%; }
        th, td { border: 1px solid #cbd5e1; font-size: 11px; padding: 7px; text-align: left; }
        th { background: #e2e8f0; color: #334155; text-transform: uppercase; }
        .totals { display: grid; gap: 8px; grid-template-columns: repeat(3, 1fr); margin-top: 12px; }
        .total { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px; }
        .note { color: #475569; font-size: 11px; line-height: 1.55; margin-top: 18px; }
        .signature { margin-top: 48px; text-align: center; }
        .line { border-top: 1px solid #0f172a; margin: 0 auto 8px; width: 320px; }
        @media print { body { margin: 18mm; } button { display: none; } }
      </style>
    </head>
    <body>
      <button onclick="window.print()" style="float:right;margin-bottom:16px">Imprimir / salvar PDF</button>
      <div class="top">
        <div>
          <div class="brand">FROID</div>
          <h1>Fatura / Recibo complementar de atendimento em saude</h1>
          <p class="note">Documento operacional gerado pelo FROID para conferencia, envio ao paciente e organizacao interna.</p>
        </div>
        <div>
          <span class="label">Emissao</span>
          <div class="value">${escapeHtml(issueDate.toLocaleDateString("pt-BR"))}</div>
          <span class="label">ID interno FROID</span>
          <div class="value">${escapeHtml(internalId)}</div>
        </div>
      </div>

      <h2>1. Dados do profissional / prestador</h2>
      <div class="box grid">
        <div><span class="label">Nome/Razao social</span><div class="value">${escapeHtml(info.name)}</div></div>
        <div><span class="label">Profissao/atividade</span><div class="value">${escapeHtml(info.role)}</div></div>
        <div><span class="label">CPF/CNPJ</span><div class="value">${escapeHtml(info.document || "--")}</div></div>
        <div><span class="label">Registro profissional</span><div class="value">${escapeHtml(info.registry || "--")}</div></div>
        <div><span class="label">Contato</span><div class="value">${escapeHtml([info.phone, info.email].filter(Boolean).join(" | ") || "--")}</div></div>
        <div><span class="label">Endereco</span><div class="value">${escapeHtml(info.address || "--")}</div></div>
        ${info.isOrganization ? `<div><span class="label">Inscricao municipal</span><div class="value">${escapeHtml(info.municipalRegistration || "--")}</div></div>` : ""}
        ${info.isOrganization ? `<div><span class="label">Regime tributario</span><div class="value">${escapeHtml(info.taxRegime || "--")}</div></div>` : ""}
      </div>

      <h2>2. Dados do paciente / pagador</h2>
      <div class="box grid">
        <div><span class="label">Paciente</span><div class="value">${escapeHtml(row.patient?.name || "--")}</div></div>
        <div><span class="label">CPF do paciente/beneficiario</span><div class="value">${escapeHtml(row.patient?.document || "--")}</div></div>
        <div><span class="label">Pagador</span><div class="value">${escapeHtml(payerName || "--")}</div></div>
        <div><span class="label">CPF/CNPJ do pagador</span><div class="value">${escapeHtml(payerDocument || "--")}</div></div>
      </div>

      <h2>3. Dados do atendimento e pagamento</h2>
      <div class="box">
        <div class="grid">
          <div><span class="label">Descricao do servico</span><div class="value">${escapeHtml(info.serviceDescription)}</div></div>
          <div><span class="label">Referencia oficial Receita Saude/NFS-e</span><div class="value">${escapeHtml(officialReference || "--")}</div></div>
          <div><span class="label">Forma de pagamento</span><div class="value">PIX / acordo profissional / conciliacao interna</div></div>
          <div><span class="label">Situacao</span><div class="value">${escapeHtml(row.status)}</div></div>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID FROID</th>
              <th>Data sessao/convite</th>
              <th>Sessoes</th>
              <th>Valor unit.</th>
              <th>Devido</th>
              <th>Recebido</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
        <div class="totals">
          <div class="total"><span class="label">Total devido</span><div class="value">${escapeHtml(row.total_due_brl)}</div></div>
          <div class="total"><span class="label">Total recebido</span><div class="value">${escapeHtml(row.total_received_brl)}</div></div>
          <div class="total"><span class="label">Pendente</span><div class="value">${escapeHtml(row.total_pending_brl)}</div></div>
        </div>
      </div>

      <h2>4. Declaracao e observacao fiscal</h2>
      <p class="note">
        Declara-se, para fins operacionais, que o atendimento acima descrito foi prestado ao paciente identificado neste documento,
        nos valores informados e conforme registros internos do FROID.
      </p>
      <p class="note">
        Quando o atendimento for prestado por profissional de saude autonomo pessoa fisica, o comprovante fiscal valido para fins
        oficiais deve ser emitido no sistema Receita Saude no momento do pagamento. Quando o atendimento for prestado por pessoa
        juridica, a emissao fiscal/NFS-e deve seguir a orientacao contabil aplicavel. Este PDF nao substitui o recibo eletronico
        oficial quando este for exigido.
      </p>
      ${info.fiscalObservation ? `<p class="note"><strong>Observacao do profissional:</strong> ${escapeHtml(info.fiscalObservation)}</p>` : ""}

      <div class="signature">
        <div class="line"></div>
        <div>${escapeHtml(info.name)}</div>
        <div>${escapeHtml(info.receiptCity || "Local de emissao")}, ${escapeHtml(issueDate.toLocaleDateString("pt-BR"))}</div>
      </div>
    </body>
  </html>`;

  const receiptWindow = window.open("", "_blank", "width=980,height=760");
  if (!receiptWindow) {
    window.alert("Nao foi possivel abrir a janela de recibo. Verifique o bloqueador de pop-ups.");
    return;
  }
  receiptWindow.document.open();
  receiptWindow.document.write(html);
  receiptWindow.document.close();
  receiptWindow.focus();
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
    label: "Media geral",
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

const KpiCard: React.FC<{
  label: string;
  value: string;
  detail: string;
  tone?: "blue" | "green" | "amber" | "red";
}> = ({ label, value, detail, tone = "blue" }) => {
  const color =
    tone === "green"
      ? "text-emerald-200"
      : tone === "amber"
        ? "text-amber-100"
        : tone === "red"
          ? "text-red-200"
          : "text-cyan-200";
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-2.5 shadow-sm">
      <FroidTooltip
        width={320}
        content={
          <div>
            <p className="font-bold text-slate-900">{label}</p>
            <p className="mt-1">{KPI_TOOLTIPS[label] || detail}</p>
          </div>
        }
      >
        <p className="inline cursor-help border-b border-dashed border-slate-500 text-[10px] font-black uppercase tracking-wider text-slate-400">
          {label}
        </p>
      </FroidTooltip>
      <p className={`mt-1.5 text-lg font-black ${color}`}>{value}</p>
      <p className="mt-1 text-[10px] leading-snug text-slate-400">{detail}</p>
    </div>
  );
};

const ScoreBar: React.FC<{ label: string; value: number; color: string }> = ({
  label,
  value,
  color,
}) => (
  <div>
    <div className="mb-1 flex items-center justify-between gap-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">
      <FroidTooltip
        width={320}
        content={
          <div>
            <p className="font-bold text-slate-900">{label}</p>
            <p className="mt-1">{SIGNAL_TOOLTIPS[label] || "Indicador medio da carteira do paciente."}</p>
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
  const [receivables, setReceivables] = useState<ReceivableRow[]>([]);
  const [receivablesSummary, setReceivablesSummary] = useState<ReceivablesSummary | null>(null);
  const [receivablesMessage, setReceivablesMessage] = useState("");
  const [receivablesLoading, setReceivablesLoading] = useState(false);
  const [professionalProfile, setProfessionalProfile] = useState<ProfessionalProfile | null>(null);
  const [reports, setReports] = useState<SessionReportRecord[]>(() =>
    loadSessionReports(),
  );
  const eventCursorRef = useRef<number | null>(null);
  const redirectingRef = useRef(false);
  const professionalName = user?.name || user?.email || "Profissional";

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

  const updateReceivable = async (
    patientKey: string,
    action: "paid" | "pending" | "partial",
  ) => {
    setReceivablesLoading(true);
    setReceivablesMessage("");
    try {
      let received_cents: number | undefined;
      if (action === "partial") {
        const typed = window.prompt("Valor recebido parcialmente em R$:", "");
        if (!typed) return;
        const normalized = typed.replace(/\./g, "").replace(",", ".");
        received_cents = Math.round(Number(normalized) * 100);
        if (!Number.isFinite(received_cents) || received_cents < 0) {
          throw new Error("Valor parcial invalido.");
        }
      }
      const response = await fetch(apiUrl("/api/professional/receivables/update"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({ patient_key: patientKey, action, received_cents }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Nao foi possivel atualizar o recebimento.");
      setReceivablesMessage("Recebimento atualizado.");
      await loadReceivables();
      window.setTimeout(() => setReceivablesMessage(""), 2500);
    } catch (error: any) {
      setReceivablesMessage(error?.message || "Falha ao atualizar recebimento.");
    } finally {
      setReceivablesLoading(false);
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
          clinical_load: Number(signal.clinicalLoad.toFixed(1)),
          communication: Number(signal.communication.toFixed(1)),
          continuity: Number(signal.continuity.toFixed(1)),
          insight: Number(signal.insight.toFixed(1)),
          dominant_zone: group.dominantZone,
          recurrent_emotion: group.recurrentEmotion,
          clinical_risk: group.clinicalRisk,
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
            clinical_load: selectedSignal
              ? Number(selectedSignal.clinicalLoad.toFixed(1))
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
            clinical_risk: selectedGroup.clinicalRisk,
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
    if (group?.patient) {
      rememberSessionPatient(sessionId, {
        id: group.patient.id,
        name: group.patient.name,
        email: group.patient.email,
        phone: group.patient.phone,
        document: group.patient.document,
        sessionMode: "presential",
        captureProfile: "patient_external_media",
      });
      setSelectedPatientKey(group.key);
    } else {
      rememberSessionPatient(sessionId, {
        name: "Paciente presencial",
        sessionMode: "presential",
        captureProfile: "patient_external_media",
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
          const response = await fetch(apiUrl("/api/session-events/latest"));
          if (!response.ok) return;
          const data = await response.json();
          eventCursorRef.current = Number(data?.latest_id || 0);
          return;
        }

        const response = await fetch(
          apiUrl(`/api/session-events?after=${eventCursorRef.current}`),
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
          setPatientActivity(`${patient} entrou na sessao. Abrindo sala profissional...`);
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
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">
              Dashboard Profissional
            </p>
            <h1 className="mt-1 text-xl font-bold text-slate-100">{professionalName}</h1>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {professionalProfile && (
              <span className="rounded-lg border border-emerald-800 bg-emerald-950 px-3 py-2 text-xs font-bold text-emerald-100">
                Saldo: {professionalProfile.remaining_sessions ?? "--"} sessoes
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
            <button
              onClick={() => nav("/settings")}
              className="rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100 hover:bg-cyan-900"
            >
              Configuracoes
            </button>
            <button
              onClick={onLogout}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 p-6">

      {patientActivity && (
        <p className="rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100">
          {patientActivity}
        </p>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-4">
      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-slate-100">Recebimentos por paciente</h2>
            <p className="mt-1 text-[11px] text-slate-400">
              Controle operacional dos valores devidos e realizados a partir dos convites e pacotes.
            </p>
          </div>
          <div className="grid min-w-[360px] grid-cols-3 gap-2 text-right text-[10px]">
            <div className="rounded border border-slate-700 bg-slate-950 px-2 py-1.5">
              <p className="font-black uppercase text-slate-500">Devido</p>
              <p className="mt-1 font-black text-cyan-200">
                {receivablesSummary?.total_due_brl || "R$ 0,00"}
              </p>
            </div>
            <div className="rounded border border-slate-700 bg-slate-950 px-2 py-1.5">
              <p className="font-black uppercase text-slate-500">Recebido</p>
              <p className="mt-1 font-black text-emerald-200">
                {receivablesSummary?.total_received_brl || "R$ 0,00"}
              </p>
            </div>
            <div className="rounded border border-slate-700 bg-slate-950 px-2 py-1.5">
              <p className="font-black uppercase text-slate-500">Pendente</p>
              <p className="mt-1 font-black text-amber-100">
                {receivablesSummary?.total_pending_brl || "R$ 0,00"}
              </p>
            </div>
          </div>
        </div>

        {receivablesMessage && (
          <p className="mt-3 rounded border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100">
            {receivablesMessage}
          </p>
        )}

        <div className="mt-3 overflow-x-auto">
          <table className="min-w-max table-auto text-left text-[10px] leading-tight">
            <thead className="text-[9px] uppercase tracking-normal text-slate-500">
              <tr>
                <th className="whitespace-nowrap py-1 pr-2">Paciente</th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Sessoes
                </th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Pacotes
                </th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Avulsas
                </th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Devido
                </th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Recebido
                </th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Pendente
                </th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Ultimo convite
                </th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Status
                </th>
                <th className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold">
                  Acoes
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {receivables.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-3 text-xs text-slate-400">
                    Nenhum recebimento registrado. Gere convites com valor de sessao para alimentar esta tabela.
                  </td>
                </tr>
              ) : (
                receivables.map((row) => (
                  <tr key={row.patient_key} className="align-top">
                    <td className="whitespace-nowrap py-1 pr-2">
                      <p className="font-black text-slate-100">
                        {row.patient?.name || "Paciente sem nome"}
                      </p>
                      <p className="text-[9px] text-slate-500">
                        {row.patient?.email || row.patient?.phone || row.patient_key}
                      </p>
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">
                      {row.session_count}
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">
                      {row.package_count}
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">
                      {row.single_count}
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold text-cyan-200">
                      {row.total_due_brl}
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold text-emerald-200">
                      {row.total_received_brl}
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 font-bold text-amber-100">
                      {row.total_pending_brl}
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1 text-slate-300">
                      {row.last_invite_at
                        ? new Date(row.last_invite_at).toLocaleDateString("pt-BR")
                        : "--"}
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[9px] font-black uppercase ${
                          RECEIVABLE_STATUS[row.status] || RECEIVABLE_STATUS.sem_valor
                        }`}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap border-l border-slate-700 px-2 py-1">
                      <div className="flex flex-wrap gap-1">
                        <button
                          type="button"
                          disabled={receivablesLoading}
                          onClick={() => void updateReceivable(row.patient_key, "paid")}
                          className="rounded border border-emerald-800 bg-emerald-950/50 px-2 py-1 text-[9px] font-bold text-emerald-100 hover:bg-emerald-900 disabled:opacity-40"
                        >
                          Recebido
                        </button>
                        <button
                          type="button"
                          disabled={receivablesLoading}
                          onClick={() => void updateReceivable(row.patient_key, "partial")}
                          className="rounded border border-amber-700 bg-amber-950/50 px-2 py-1 text-[9px] font-bold text-amber-100 hover:bg-amber-900 disabled:opacity-40"
                        >
                          Parcial
                        </button>
                        <button
                          type="button"
                          disabled={receivablesLoading}
                          onClick={() => void updateReceivable(row.patient_key, "pending")}
                          className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[9px] font-bold text-slate-300 hover:bg-slate-800 disabled:opacity-40"
                        >
                          Pendente
                        </button>
                        <button
                          type="button"
                          onClick={() => openReceiptPrintWindow(row, professionalProfile, user)}
                          className="rounded border border-cyan-700 bg-cyan-950/50 px-2 py-1 text-[9px] font-bold text-cyan-100 hover:bg-cyan-900"
                        >
                          Recibo
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-slate-100">Meus Pacientes</h2>
          <p className="mt-1 text-[11px] text-slate-400">
            Ultimas sessoes, metricas medias e resultado clinico resumido.
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <button
            onClick={() => openPatientRegistration()}
            className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-800"
          >
            + Novo Paciente
          </button>
          <button
            onClick={() => startPresentialSession()}
            className="rounded-lg border border-emerald-700 bg-emerald-950 px-3 py-2 text-xs font-bold text-emerald-100 hover:bg-emerald-900"
          >
            + Sessao Presencial
          </button>
          <button
            onClick={() => startPresentialMobileSession()}
            className="rounded-lg border border-violet-700 bg-violet-950 px-3 py-2 text-xs font-bold text-violet-100 hover:bg-violet-900"
          >
            + Presencial com Celular
          </button>
          <button
            onClick={() => nav(`/session/${makeId()}`)}
            className="rounded-lg border border-blue-800 bg-blue-950 px-3 py-2 text-xs font-bold text-blue-100 hover:bg-blue-900"
          >
            + Nova Sessao Direta
          </button>
        </div>
        </div>
      </section>

      <section className="space-y-4">
        {patientGroups.length === 0 && (
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-xs text-slate-400">
            Nenhum paciente com relatorio encontrado. Finalize uma sessao para
            alimentar o dashboard profissional.
          </div>
        )}

        {patientGroups.map((group) => {
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
                  {group.patient.name || "Paciente sem nome"}
                </h3>
                <p className="mt-1 text-xs text-slate-400">
                  CPF: {group.patient.document || "Nao informado"} - {group.totalSessions} sessoes
                </p>
              </div>
              <div className="min-w-[320px] flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-[11px] text-slate-300">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span>
                    <strong>Acao sugerida:</strong> {signal.action}
                  </span>
                  <span>
                    <strong>Qualidade:</strong> {signal.qualityLabel}
                  </span>
                  <span>
                    <strong>Estado atual:</strong> {signal.state}
                  </span>
                </div>
              </div>
              <div className="flex h-fit flex-wrap justify-end gap-2">
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
                  className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-800"
                >
                  Convite
                </button>
                <button
                  onClick={() => startPresentialSession(group)}
                  className="rounded-lg border border-emerald-700 bg-emerald-950 px-3 py-2 text-xs font-bold text-emerald-100 hover:bg-emerald-900"
                >
                  Presencial
                </button>
                <button
                  onClick={() => startPresentialMobileSession(group)}
                  className="rounded-lg border border-violet-700 bg-violet-950 px-3 py-2 text-xs font-bold text-violet-100 hover:bg-violet-900"
                >
                  Celular PC
                </button>
                <button
                  onClick={() => {
                    setSelectedPatientKey(group.key);
                    nav(`/patients/${encodeURIComponent(group.key)}`);
                  }}
                  className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
                >
                  Ver Detalhes
                </button>
              </div>
            </div>

            <div className="mt-3 rounded-lg border border-slate-700 bg-slate-950 p-3">
              <p className="mb-2 text-xs font-black uppercase tracking-wide text-cyan-200">
                Indicadores medios de todas as sessoes
              </p>
              <div className="grid gap-2 md:grid-cols-5">
                <ScoreBar label="Atencao" value={signal.attentionIndex} color="#ef4444" />
                <ScoreBar label="Carga" value={signal.clinicalLoad} color="#f97316" />
                <ScoreBar label="Comunicacao" value={signal.communication} color="#0ea5e9" />
                <ScoreBar label="Continuidade" value={signal.continuity} color="#22c55e" />
                <ScoreBar label="Insight" value={signal.insight} color="#8b5cf6" />
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
                                  {METRIC_TOOLTIPS[cell.key] || "Metrica media consolidada das sessoes do paciente."}
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
                        Media
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
                Indicadores das ultimas 3 sessoes
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
                                  {METRIC_TOOLTIPS[cell.key] || "Metrica desta sessao no acompanhamento do paciente."}
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
                              Ver
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
                      Resultado da sessao {shortId(report.sessionId)}:
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

        <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4 shadow-sm">
            <div className="mb-3">
              <h2 className="text-sm font-bold text-slate-100">Resumo profissional</h2>
              <p className="mt-1 text-[11px] text-slate-400">
                Indicadores consolidados da carteira em acompanhamento.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <KpiCard
                label="Pacientes"
                value={String(portfolio.totalPatients)}
                detail="Carteira visivel apos filtros locais."
              />
              <KpiCard
                label="Atencao media"
                value={scoreText(portfolio.meanAttention)}
                detail="Indice global de prioridade profissional."
                tone="red"
              />
              <KpiCard
                label="Carga clinica"
                value={scoreText(portfolio.meanClinicalLoad)}
                detail="IPM, IDM, dissonancias e qualidade."
                tone="amber"
              />
              <KpiCard
                label="Comunicacao"
                value={scoreText(portfolio.meanCommunication)}
                detail="Resumo, cortes e anotacoes disponiveis."
              />
              <KpiCard
                label="Continuidade"
                value={scoreText(portfolio.meanContinuity)}
                detail="Sessoes, analises e status operacional."
                tone="green"
              />
              <KpiCard
                label="Para revisao"
                value={String(portfolio.reviewCount)}
                detail="Pacientes em revisar ou alta prioridade."
                tone="red"
              />
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4 shadow-sm">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-bold text-slate-100">FROID Explica</h2>
                <p className="mt-0.5 text-[11px] text-slate-400">
                  {selectedGroup
                    ? "Contexto carregado a partir do paciente selecionado."
                    : "Passe o mouse sobre um paciente para carregar o contexto."}
                </p>
              </div>
              <button
                onClick={() => nav("/settings")}
                className="rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-1.5 text-[11px] font-bold text-cyan-100 hover:bg-cyan-900"
              >
                Meus Prompts...
              </button>
            </div>
            {selectedGroup ? (
              <div className="max-h-[520px] overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 px-2 pb-2 pr-1">
                <AIInsights
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
                  messagesClassName="min-h-48 max-h-72 bg-slate-800/80 text-slate-200"
                />
              </div>
            ) : (
              <div className="rounded-lg border border-slate-700 bg-slate-950 p-4 text-xs leading-relaxed text-slate-400">
                Selecione um paciente na coluna principal para habilitar perguntas
                ao FROID Explica com contexto clinico longitudinal.
              </div>
            )}
          </section>
        </aside>
      </div>

      </main>
    </div>
  );
};
