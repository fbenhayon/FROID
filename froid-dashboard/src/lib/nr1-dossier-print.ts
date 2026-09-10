import { buildBrandedPrintable, escapeHtml, openPrintable } from "./report-pdf";

export type Nr1DossierPayload = {
  document: { title: string; scope: string; schema_version?: string; generated_at?: string };
  organization: { legal_name?: string; organization_name?: string };
  normative_basis: Array<{ reference: string; purpose: string; url: string }>;
  response_protocol: string[];
  privacy: Record<string, string>;
  completeness: {
    status: "complete" | "attention";
    gaps: string[];
    counts: Record<string, number>;
  };
  records: Record<string, Array<Record<string, unknown>>>;
};

type VersionIdentity = {
  version?: number;
  content_sha256: string;
  previous_sha256?: string | null;
  sealed_at?: string | null;
  integrity_verified?: boolean;
};

const COUNT_LABELS: Record<string, string> = {
  active_units: "Unidades e grupos ativos",
  published_criteria_versions: "Versões publicadas dos critérios do GRO",
  closed_campaigns: "Campanhas encerradas",
  aep_documents: "AEPs concluídas ou em curso",
  aep_evidence: "Evidências metodológicas da AEP",
  worker_participation_records: "Registros de consulta e participação",
  inventory_rows: "Riscos documentados no inventário",
  inventory_history_rows: "Versões históricas do inventário",
  action_plan_items: "Medidas no plano de ação",
  effectiveness_reviews: "Revisões de eficácia",
  corrections_required: "Correções requeridas",
};

const date = (value?: unknown) => {
  if (!value) return "não registrado";
  const parsed = new Date(String(value));
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString("pt-BR");
};

const value = (input: unknown) => {
  if (input === null || input === undefined || input === "") return "não registrado";
  if (typeof input === "boolean") return input ? "sim" : "não";
  if (Array.isArray(input)) return input.map(String).join("; ") || "não registrado";
  if (typeof input === "object") return JSON.stringify(input);
  return String(input);
};

const cell = (input: unknown) => escapeHtml(value(input));

const table = (headers: string[], rows: unknown[][]) => {
  if (!rows.length) return `<p class="ausente">Nenhum registro nesta seção.</p>`;
  return `<table><thead><tr>${headers.map((item) => `<th>${escapeHtml(item)}</th>`).join("")}</tr></thead>`
    + `<tbody>${rows.map((row) => `<tr>${row.map((item) => `<td>${cell(item)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
};

const section = (number: string, title: string, body: string) =>
  `<section><div class="cab"><span class="num">${number}</span><h2>${escapeHtml(title)}</h2></div>${body}</section>`;

export function buildNr1DossierPrintable(
  payload: Nr1DossierPayload,
  identity: VersionIdentity,
): string {
  const organization = payload.organization.organization_name
    || payload.organization.legal_name
    || "Organização não registrada";
  const version = identity.version ? `Versão ${identity.version}` : "Prévia não registrada";
  const records = payload.records || {};
  const gaps = payload.completeness.gaps || [];
  const integrity = identity.integrity_verified === false
    ? "A conferência do conteúdo armazenado divergiu do hash registrado. Não utilize este documento."
    : identity.version
      ? "Integridade conferida: a recomputação do conteúdo canônico corresponde ao SHA-256 registrado. A versão é preservada sem UPDATE ou DELETE pelo papel operacional e está encadeada à versão anterior."
      : "Esta é uma prévia. O SHA-256 identifica exatamente o conteúdo exibido, mas a versão ainda não integra o histórico append-only.";

  const cover = `<section>
    <div class="tags"><span class="tag destaque">FROID NR-1 / ISO 45003</span><span class="tag">${escapeHtml(version)}</span></div>
    <h1>Dossiê de evidências do processo psicossocial</h1>
    <p class="sub">${escapeHtml(payload.document.scope)}</p>
    <div class="meta"><div><dt>Organização</dt><dd>${escapeHtml(organization)}</dd><dt>Situação</dt><dd>${escapeHtml(payload.completeness.status === "complete" ? "Cadeia documental completa" : "Pontos de atenção")}</dd></div>
    <div><dt>Registro</dt><dd>${escapeHtml(version)}</dd><dt>Data do registro</dt><dd>${escapeHtml(date(identity.sealed_at))}</dd></div></div>
    <div class="integridade"><b>SHA-256 do conteúdo canônico</b><code>${escapeHtml(identity.content_sha256)}</code><p>${escapeHtml(integrity)}</p>${identity.previous_sha256 ? `<p><b>Encadeado ao SHA-256 anterior:</b> <code>${escapeHtml(identity.previous_sha256)}</code></p>` : ""}</div>
  </section>`;

  const counts = Object.entries(payload.completeness.counts || {});
  const map = section("01", "Mapa das evidências consolidadas",
    table(["Componente probatório", "Registros"], counts.map(([key, count]) => [COUNT_LABELS[key] || key, count])));

  const readiness = section("02", "Prontidão e lacunas documentais",
    gaps.length
      ? `<ul>${gaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join("")}</ul>`
      : "<p>As etapas previstas possuem registros vinculados. A organização deve conferir conteúdo, competência profissional e assinatura aplicável antes da apresentação externa.</p>");

  const campaigns = section("03", "Campanhas e representatividade", table(
    ["Campanha", "Situação", "Respostas substantivas", "Efetivo-alvo"],
    (records.campaigns || []).map((item) => [item.title, item.status, item.substantive_responses, item.target_headcount]),
  ));
  const aep = section("04", "Avaliação Ergonômica Preliminar", table(
    ["Unidade", "Situação", "Descrição do trabalho real", "Exposição", "Responsável"],
    (records.aep || []).map((item) => [item.unit_name, item.status, item.real_work_description, [item.exposure_duration, item.exposure_frequency, item.exposure_intensity].filter(Boolean).join(" · "), [item.responsible_name, item.responsible_qualification].filter(Boolean).join(" · ")]),
  ));
  const evidence = section("05", "Evidências metodológicas da AEP", table(
      ["Método", "Data", "Síntese", "Referência"],
      (records.evidence || []).map((item) => [item.method, date(item.collected_on), item.summary, item.evidence_reference]),
    ));
  const participation = section("06", "Consulta, participação e comunicação", table(
      ["Unidade", "Registro", "Data", "Assunto", "Participantes/evidência"],
      (records.worker_participation || []).map((item) => [item.unit_name, item.record_type, date(item.occurred_on), item.subject, [item.attendee_count, item.evidence_reference].filter((entry) => entry !== null && entry !== undefined && entry !== "").join(" · ")]),
    ));
  const inventory = section("07", "Inventário de riscos", table(
    ["Unidade/recorte", "Perigo ou dimensão", "Classificação", "Expostos", "Revisão"],
    (records.inventory || []).map((item) => [item.unit_name, item.dimension_title || item.hazard_description, item.risk_classification || item.risk_level, item.exposed_workers, date(item.review_due_at)]),
  ));
  const actions = section("08", "Plano de ação e acompanhamento", table(
    ["Medida", "Situação", "Responsável", "Prazo", "Aferição"],
    (records.action_plan || []).map((item) => [item.measure || item.plan_action, item.status, item.responsible_membership_id ? "vínculo responsável registrado" : null, date(item.due_date), [item.monitoring_method, item.result_measurement].filter(Boolean).join(" · ")]),
  ));
  const effectiveness = section("09", "Reavaliação e eficácia", table(
    ["Medida/risco", "Resultado", "Antes", "Depois", "Correção"],
    (records.effectiveness || []).map((item) => [item.dimension_title, item.verdict || item.measure_efficacy, item.baseline_mean, item.followup_mean, item.requires_correction]),
  ));
  const protocol = section("10", "Roteiro de apresentação à fiscalização",
    `<ol>${payload.response_protocol.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>`);
  const basis = section("11", "Base normativa e limites da prova",
    payload.normative_basis.map((item) => `<p><b>${escapeHtml(item.reference)}</b><br>${escapeHtml(item.purpose)}<br><span class="url">${escapeHtml(item.url)}</span></p>`).join("")
      + `<div class="limite"><b>Limites:</b> o SHA-256 demonstra integridade, e o encadeamento append-only evidencia alteração ou substituição de versões. Esses controles não identificam o signatário e não substituem a assinatura eletrônica exigida pela política documental da organização. O dossiê contém somente resultados agregados; nenhuma resposta individual de trabalhador integra a exportação.</div>`);

  const shortHash = identity.content_sha256.slice(0, 12);
  return buildBrandedPrintable({
    title: `Dossiê NR-1 — ${organization}`,
    blocks: [cover, map, readiness, campaigns, aep, evidence, participation, inventory, actions, effectiveness, protocol, basis],
    footer: `FROID NR-1 / ISO 45003 · ${version} · SHA-256 ${shortHash}…`,
    finalFooter: `FROID NR-1 / ISO 45003 · ${organization} · ${version} · SHA-256 ${shortHash}…`,
    headerLabel: organization,
    extraCss: `.integridade{margin-top:14px;border:1px solid #0E7490;border-left:4px solid #0891B2;border-radius:5px;padding:11px 13px;background:#ECFEFF;font-size:8pt}.integridade code{display:block;margin:5px 0;overflow-wrap:anywhere;color:#0F172A;font-size:7.5pt}.integridade p{margin:4px 0 0}.ausente{color:#6C757D;font-style:italic}.url{font-size:7pt;color:#0369A1;overflow-wrap:anywhere}h3{margin:12px 0 4px;color:#0F172A;font-size:9pt}ol,ul{margin:5px 0;padding-left:20px}li{margin:0 0 6px}`,
  });
}

export function printNr1Dossier(payload: Nr1DossierPayload, identity: VersionIdentity): boolean {
  return openPrintable(buildNr1DossierPrintable(payload, identity));
}
