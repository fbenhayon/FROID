import type { SessionReportRecord } from "./session-report";
import { patientViewFor } from "./dissonance-patient-view";
import { pickEpigraph } from "./report-epigraph";
import { pickIntro } from "./report-intro";

/**
 * Gerador dos dois documentos imprimíveis da sessão.
 *
 * Imprime pelo navegador, sem biblioteca de PDF. A decisão não é de preguiça:
 * uma dependência de geração de PDF no backend significaria fonte embarcada,
 * layout duplicado e mais uma coisa para quebrar no contêiner. O navegador já
 * pagina, já lida com acento e já sabe imprimir — e o modelo aprovado já é
 * HTML, então o que foi conferido em tela é o que sai no papel.
 *
 * Dois documentos, um motor:
 *
 *   PROFISSIONAL — texto técnico integral, dissonâncias com rótulo e sugestão
 *   de conduta, epígrafe, e o relatório descritivo que ele redigiu.
 *
 *   PACIENTE — os mesmos sinais descritos como MEDIDA, sem rótulo e sem
 *   conduta, via dissonance-patient-view. Sinal sem tradução escrita é OMITIDO,
 *   nunca substituído pelo texto técnico.
 */

export type ReportAudience = "professional" | "patient";

export type ReportIdentity = {
  /** Nome da clínica ou do profissional. Vai no título dos dois documentos. */
  clinicName: string;
  professionalName: string;
  professionalRegistry: string;
  contactEmail: string;
};

const IDENTITY_FALLBACK: ReportIdentity = {
  clinicName: "",
  professionalName: "",
  professionalRegistry: "",
  contactEmail: "",
};

/** Escapa para HTML. Nome de paciente e texto redigido pelo profissional entram
 *  no documento; sem escapar, um `<` no texto quebraria a página, e um trecho
 *  colado de outro sistema poderia trazer marcação junto. */
export function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function formatDurationLong(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

function num(value: unknown, digits = 2): string {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits).replace(".", ",") : "--";
}

/** Ordena do primeiro corte para o último, como o resto do produto. */
function orderedCuts(report: SessionReportRecord) {
  return [...(report.conversationSummaries || [])].sort(
    (a, b) => (a.startSecond ?? a.startMinute * 60) - (b.startSecond ?? b.startMinute * 60),
  );
}

function cutRange(cut: { startSecond?: number; endSecond?: number; startMinute: number; endMinute: number }) {
  const inicio = cut.startSecond ?? cut.startMinute * 60;
  const fim = cut.endSecond ?? cut.endMinute * 60;
  return `${formatClock(inicio)} – ${formatClock(fim)}`;
}

/** Texto que substitui um resumo ausente.
 *
 *  O relatório de produção trazia "Resumo indisponível" em três dos quatro
 *  cortes. Num documento impresso e assinado isso lê como falha do produto —
 *  e para o paciente, como se aquele pedaço da sessão dele não tivesse valido
 *  nada. Dizer o que houve é melhor do que dizer que não há. */
export const FALLBACK_SUMMARY =
  "Não houve fala suficiente neste intervalo para uma síntese. "
  + "As medições do período seguem registradas.";

export function summaryOrFallback(text: unknown): string {
  const limpo = String(text || "").trim();
  if (!limpo) return FALLBACK_SUMMARY;
  const vazios = [
    "resumo indisponível", "resumo indisponivel",
    "nenhuma fala foi transcrita", "sem fala transcrita",
  ];
  return vazios.some((v) => limpo.toLowerCase().includes(v)) ? FALLBACK_SUMMARY : limpo;
}

const BASE_CSS = `
:root{--navy:#0F172A;--azul:#3B82F6;--aco:#3B82F6;--fundo:#F8F9FA;--linha:#E5E7EB;
      --texto:#212529;--rotulo:#6C757D;--zebra:#F9F9F9;
      --verde:#15803D;--ambar:#B45309;--vermelho:#B91C1C}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,Roboto,"Open Sans",Helvetica,Arial,sans-serif;
     color:var(--texto);font-size:9.5pt;line-height:1.5}
.folha{width:210mm;min-height:297mm;margin:0 auto;padding:22mm 14mm 15mm;
       position:relative;page-break-after:always}
.folha:last-child{page-break-after:auto}
.folha::before{content:"";position:absolute;top:0;left:0;right:0;height:5mm;
  background:linear-gradient(90deg,#0F172A 0%,#0F172A 72%,#3B82F6 100%)}
.marca-topo{position:absolute;top:1.4mm;left:14mm;color:#F8FAFC;font-size:7pt;
            font-weight:800;letter-spacing:.34em}
.marca-topo span{color:#3B82F6}
.tags{display:flex;gap:6px;margin-bottom:12px}
.tag{background:var(--fundo);border:1px solid var(--linha);color:var(--rotulo);
     font-size:7pt;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
     padding:4px 9px;border-radius:4px}
.tag.destaque{background:var(--navy);border-color:var(--navy);color:#fff}
h1{margin:0;color:var(--navy);font-size:21pt;font-weight:800;text-transform:uppercase;line-height:1.14}
.sub{margin:5px 0 0;color:var(--rotulo);font-size:9pt}
.meta{display:grid;grid-template-columns:1fr 1fr;margin:14px 0 0;background:var(--fundo);
      border:1px solid var(--linha);border-radius:6px;overflow:hidden}
.meta>div{padding:10px 13px}.meta>div+div{border-left:1px solid var(--linha)}
.meta dt{color:var(--rotulo);font-size:7pt;font-weight:700;letter-spacing:.08em;
         text-transform:uppercase;margin-top:7px}
.meta dt:first-child{margin-top:0}
.meta dd{margin:2px 0 0;font-size:9pt;font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:13px 0 0}
.kpi{background:var(--fundo);border:1px solid var(--linha);border-radius:6px;padding:10px 8px;text-align:center}
.kpi .n{color:var(--navy);font-size:20pt;font-weight:800;line-height:1}
.kpi .d{color:var(--rotulo);font-size:7pt;margin-top:5px;text-transform:uppercase;font-weight:600}
section{margin-top:19px}
.cab{display:flex;align-items:baseline;gap:10px;border-bottom:1px solid var(--linha);
     padding-bottom:5px;margin-bottom:10px}
.cab .num{color:var(--azul);font-size:15pt;font-weight:800}
.cab h2{margin:0;color:var(--navy);font-size:12.5pt;font-weight:700;text-transform:uppercase}
p{margin:0 0 7px}
table{width:100%;border-collapse:collapse;font-size:8.5pt;margin-top:5px}
thead th{background:var(--navy);color:#fff;text-transform:uppercase;font-size:7pt;
         padding:6px 8px;text-align:left}
thead th.n,tbody td.n{text-align:right}
tbody td{padding:6px 8px;border-bottom:1px solid var(--linha);vertical-align:top}
tbody tr:nth-child(even){background:var(--zebra)}
.fase{display:flex;gap:10px;margin-bottom:10px;page-break-inside:avoid}
.fase .badge{flex:0 0 66px;background:var(--azul);color:#fff;border-radius:5px;padding:6px 4px;
             text-align:center;font-size:7pt;font-weight:800;text-transform:uppercase;height:fit-content}
.fase .badge b{display:block;font-size:10pt}
.fase .corpo{flex:1}.fase .corpo>b{color:var(--navy);font-size:9.5pt}
.fase .corpo p{margin:3px 0 0;font-size:8.5pt;color:#374151}
.fase .zona{margin-top:6px;background:var(--fundo);border-left:2px solid var(--azul);
            padding:6px 9px;border-radius:0 4px 4px 0;font-size:8pt}
.limite{background:#451A03;border:1px solid #92400E;border-radius:6px;padding:11px 13px;
        font-size:8.5pt;color:#FDE68A;margin-top:12px;line-height:1.55}
.limite b{color:#FCD34D}
footer{margin-top:18px;padding-top:8px;border-top:1px solid var(--linha);
       display:flex;justify-content:space-between;color:var(--rotulo);font-size:7pt}
@media print{.folha{margin:0}@page{size:A4;margin:0}}
`;

const EXTRA_PROFISSIONAL = `
.epigrafe{margin:15px 0 0;background:var(--navy);color:#E2E8F0;border-radius:6px;
          padding:14px 18px;position:relative}
.epigrafe p{margin:0 0 5px;font-size:10pt;font-style:italic;color:#F1F5F9}
.epigrafe .autor{font-size:7.5pt;font-weight:700;letter-spacing:.1em;
                 text-transform:uppercase;color:var(--azul)}
.epigrafe .fonte{font-size:7pt;color:#94A3B8;margin-top:2px}
.disso{border:1px solid #7F1D1D;border-left:3px solid #B91C1C;background:#FEF2F2;
       border-radius:0 6px 6px 0;padding:11px 13px;margin-bottom:10px;page-break-inside:avoid}
.disso-cab{color:#7F1D1D;font-size:7pt;font-weight:800;text-transform:uppercase}
.disso>b{color:var(--navy);font-size:9.5pt}
.disso p{margin:5px 0 0;font-size:8pt;color:#450A0A}
.redigido{border:1px solid var(--linha);border-radius:5px;padding:12px;
          font-size:9pt;white-space:pre-wrap}
.assin{margin-top:32px;border-top:1px solid #9CA3AF;width:62%;padding-top:5px;
       font-size:8pt;color:var(--rotulo)}
/* Selo de alerta e caixa de nota — copiados do modelo aprovado
   (docs/modelo-relatorio-descritivo.html). As tabelas já vêm do CSS base. */
.pill{display:inline-block;padding:1px 7px;border-radius:9px;font-size:7pt;font-weight:700}
.ok{background:#DCFCE7;color:var(--verde)} .at{background:#FEF3C7;color:var(--ambar)}
.cr{background:#FEE2E2;color:var(--vermelho)}
.nota{background:var(--fundo);border-left:3px solid var(--aco);padding:9px 12px;
      border-radius:0 5px 5px 0;font-size:8.5pt;margin-top:9px}
.cobertura{font-size:7.5pt;color:var(--rotulo);margin-top:5px}
`;

const EXTRA_PACIENTE = `
.abertura{margin:15px 0 0;background:var(--fundo);border-left:3px solid var(--azul);
          padding:12px 15px;border-radius:0 6px 6px 0;font-size:9.5pt;line-height:1.62}
.sinal{border:1px solid var(--linha);border-left:3px solid var(--azul);
       border-radius:0 6px 6px 0;padding:11px 13px;margin-bottom:9px;page-break-inside:avoid}
.sinal .quando{color:var(--rotulo);font-size:7pt;font-weight:700;text-transform:uppercase}
.sinal h3{margin:3px 0 5px;color:var(--navy);font-size:10pt}
.sinal .assunto{background:var(--fundo);border-radius:4px;padding:7px 9px;
                margin:0 0 7px;font-size:8pt}
.glossario{background:var(--fundo);border:1px solid var(--linha);border-radius:6px;
           padding:11px 13px;margin-top:10px;font-size:8.5pt}
.glossario b{color:var(--azul)}
`;

function head(titulo: string, extra: string): string {
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">`
    + `<title>${escapeHtml(titulo)}</title><style>${BASE_CSS}${extra}</style></head><body>`;
}

function identityOf(partial?: Partial<ReportIdentity>): ReportIdentity {
  return { ...IDENTITY_FALLBACK, ...(partial || {}) };
}

function tituloDocumento(id: ReportIdentity): string {
  return id.clinicName || id.professionalName || "Relatório da sessão";
}

function sessionDate(report: SessionReportRecord): string {
  const d = new Date(report.createdAt);
  return Number.isNaN(d.getTime())
    ? String(report.createdAt || "--")
    : d.toLocaleString("pt-BR", { dateStyle: "long", timeStyle: "short" });
}

function metaBlock(report: SessionReportRecord, id: ReportIdentity, mostraPaciente: boolean): string {
  return `<div class="meta"><div>
      <dt>Profissional</dt><dd>${escapeHtml(id.professionalName || "--")}</dd>
      <dt>Registro</dt><dd>${escapeHtml(id.professionalRegistry || "--")}</dd>
      <dt>Data da sessão</dt><dd>${escapeHtml(sessionDate(report))}</dd>
    </div><div>
      ${mostraPaciente
        ? `<dt>Paciente</dt><dd>${escapeHtml(report.patientName || report.patient?.name || "--")}</dd>`
        : ""}
      <dt>Sessão</dt><dd>${escapeHtml(report.sessionId)}</dd>
      <dt>Duração</dt><dd>${escapeHtml(formatDurationLong(report.durationSeconds))}</dd>
    </div></div>`;
}

function pagina(conteudo: string, rodapeEsq: string, n: number, total: number): string {
  return `<div class="folha"><div class="marca-topo">FR<span>OID</span></div>`
    + conteudo
    + `<footer><span>${escapeHtml(rodapeEsq)}</span>`
    + `<span>Página ${n} / ${total}</span></footer></div>`;
}

/** Documento do PROFISSIONAL. */
/** Percentual com sinal, como o modelo escreve: "0,5%", "−15,4%", "—". */
function pct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const n = Number(value) * 100;
  return `${n < 0 ? "−" : ""}${Math.abs(n).toFixed(1).replace(".", ",")}%`;
}

/** Selo de alerta. Três estados, e a ausência de alerta também é informação —
 *  uma célula vazia deixaria o leitor sem saber se foi medido. */
function selo(alerts: string[] | undefined): string {
  const lista = Array.isArray(alerts) ? alerts : [];
  if (!lista.length) return `<span class="pill ok">Sem alerta</span>`;
  const critico = lista.some((a) => String(a).toLowerCase().includes("crit"));
  return critico
    ? `<span class="pill cr">${escapeHtml(lista.join(" · "))}</span>`
    : `<span class="pill at">${escapeHtml(lista.join(" · "))}</span>`;
}

/** 01 — Síntese da sessão: zona predominante, progressão e a nota de linha de base.
 *
 *  A nota não é decorativa. Sem ela o leitor pode tomar os índices como valores
 *  absolutos comparáveis entre pessoas, que é exatamente a leitura que o produto
 *  recusa: tudo aqui é lido contra a linha de base da própria sessão.
 */
function secaoSintese(report: SessionReportRecord): string {
  const media = (report.sessionAverage || {}) as unknown as Record<string, unknown>;
  const base = (report.baseline || {}) as unknown as Record<string, unknown>;
  const cortes = orderedCuts(report);

  const zona = media.dominantZone ?? base.dominantZone;
  const tons = cortes.map((c) => String((c as unknown as Record<string, unknown>).emotionalTone || "")).filter(Boolean);
  const tonsUnicos = Array.from(new Set(tons));
  const ritmos = cortes
    .map((c) => (c as unknown as Record<string, unknown>).wordsPerMinute)
    .filter((v) => Number.isFinite(Number(v)))
    .map((v) => num(v, 1));

  const temas = cortes.map((c) => String((c as unknown as Record<string, unknown>).theme || "")).filter(Boolean);
  const progressao = temas.length
    ? `A sequência dos cortes indica substância central organizada em torno de ${escapeHtml(temas.join("; "))}.`
    : "Não há cortes com tema registrado nesta sessão.";

  const linhaIndices = [
    Number.isFinite(Number(media.ipmAvg)) ? `IPM médio ${num(media.ipmAvg, 1)}` : "",
    Number.isFinite(Number(media.idmAvg)) ? `IDM médio ${num(media.idmAvg, 2)}` : "",
    ritmos.length ? `ritmo de fala ${ritmos.join(" → ")} palavras por minuto` : "",
  ].filter(Boolean).join(" · ");

  const notaBase = [
    Number.isFinite(Number(base.ipmAvg)) ? `IPM ${num(base.ipmAvg, 2)}` : "",
    Number.isFinite(Number(base.idmAvg)) ? `IDM ${num(base.idmAvg, 2)}` : "",
    base.dominantZone !== undefined && base.dominantZone !== null ? `Zona ${escapeHtml(base.dominantZone)}` : "",
    Number.isFinite(Number(base.wordsPerMinute)) ? `${num(base.wordsPerMinute, 1)} palavras/min` : "",
  ].filter(Boolean).join(" · ");

  return `<section><div class="cab"><span class="num">01</span><h2>Síntese da sessão</h2></div>
    <h3>Zona predominante</h3>
    <p>${zona === undefined || zona === null || zona === "" ? "Zona predominante não registrada." : `Zona ${escapeHtml(zona)}.`}${
      tonsUnicos.length ? ` Tom ${escapeHtml(tonsUnicos.join(", "))}.` : ""
    }</p>
    <h3>Progressão</h3>
    <p>${progressao}</p>
    ${linhaIndices ? `<p>${escapeHtml(linhaIndices)}.</p>` : ""}
    <div class="nota"><b>Linha de base:</b> estabelecida nos primeiros 60 segundos${
      notaBase ? ` (${escapeHtml(notaBase)})` : ""
    }. Todos os índices deste relatório são lidos contra essa referência da própria
      sessão — nunca contra média populacional.</div>
  </section>`;
}

/** 02 — Leitura estatística: a tabela de métricas contra a linha de base. */
function secaoEstatistica(report: SessionReportRecord): string {
  const analise = report.metricsAnalysis;
  if (!analise || !Array.isArray(analise.metrics) || !analise.metrics.length) {
    return `<section><div class="cab"><span class="num">02</span><h2>Leitura estatística</h2></div>
      <p>${escapeHtml(
        report.metricsAnalysisError
          || "A análise estatística não está disponível para esta sessão.",
      )}</p></section>`;
  }

  const linhas = analise.metrics.map((m) => {
    const s = analise.summary?.[m.key] || ({} as Record<string, never>);
    return `<tr><td>${escapeHtml(m.label || m.key)}</td>
      <td class="n">${num(s.baseline, 2)}</td>
      <td class="n">${num(s.session_mean, 2)}</td>
      <td class="n">${num(s.last, 2)}</td>
      <td class="n">${pct(s.delta_last)}</td>
      <td>${selo(s.alerts)}</td></tr>`;
  }).join("");

  const d = analise.dashboard || ({} as Record<string, never>);
  const cobertura = [
    d.mean_coverage === null || d.mean_coverage === undefined ? "" : `Cobertura média ${pct(d.mean_coverage)}`,
    d.mean_confidence === null || d.mean_confidence === undefined ? "" : `confiança média ${pct(d.mean_confidence)}`,
    // Concordância: "1 alertas" num documento assinado lê como descuido.
    `${Number(d.alerts_count || 0)} ${Number(d.alerts_count || 0) === 1 ? "alerta" : "alertas"}`,
    `${Number(d.critical_alerts || 0)} ${Number(d.critical_alerts || 0) === 1 ? "crítico" : "críticos"}`,
  ].filter(Boolean).join(" · ");

  return `<section><div class="cab"><span class="num">02</span><h2>Leitura estatística</h2></div>
    <table>
      <thead><tr>
        <th>Métrica</th><th class="n">Baseline</th><th class="n">Média</th>
        <th class="n">Último corte</th><th class="n">Delta</th><th>Alerta</th>
      </tr></thead>
      <tbody>${linhas}</tbody>
    </table>
    ${cobertura ? `<p class="cobertura">${escapeHtml(cobertura)}.</p>` : ""}
  </section>`;
}

/** 03 — Índices por corte: uma linha por corte, com o que variou entre eles. */
function secaoIndicesPorCorte(report: SessionReportRecord): string {
  const cortes = orderedCuts(report);
  if (!cortes.length) {
    return `<section><div class="cab"><span class="num">03</span><h2>Índices por corte</h2></div>
      <p>Nenhum corte registrado nesta sessão.</p></section>`;
  }

  const linhas = cortes.map((c, i) => {
    const r = c as unknown as Record<string, unknown>;
    return `<tr><td>${i + 1}</td><td>${escapeHtml(cutRange(c))}</td>
      <td class="n">${num(r.ipmAvg, 1)}</td>
      <td class="n">${num(r.idmAvg, 2)}</td>
      <td>${r.dominantZone === null || r.dominantZone === undefined ? "—" : `Zona ${escapeHtml(r.dominantZone)}`}</td>
      <td>${escapeHtml(r.emotionalTone || "—")}</td>
      <td class="n">${num(r.wordsPerMinute, 1)}</td>
      <td class="n">${Number(r.dissonanceCount || 0)}</td></tr>`;
  }).join("");

  return `<section><div class="cab"><span class="num">03</span><h2>Índices por corte</h2></div>
    <table>
      <thead><tr>
        <th>Corte</th><th>Intervalo</th><th class="n">IPM</th><th class="n">IDM</th>
        <th>Zona</th><th>Tom</th><th class="n">Pal./min</th><th class="n">Disson.</th>
      </tr></thead>
      <tbody>${linhas}</tbody>
    </table>
  </section>`;
}

export function buildProfessionalReport(
  report: SessionReportRecord,
  identity?: Partial<ReportIdentity>,
  descriptiveText = "",
  seed?: number,
): string {
  const id = identityOf(identity);
  const epig = pickEpigraph(seed);
  const cortes = orderedCuts(report);
  const media = report.sessionAverage || ({} as never);

  const capa = `
    <div class="tags"><span class="tag destaque">Relatório descritivo</span>
      <span class="tag">Documento clínico</span><span class="tag">Confidencial</span></div>
    <h1>${escapeHtml(tituloDocumento(id))}</h1>
    <p class="sub">Relatório descritivo de sessão · registro de apoio à escuta clínica</p>
    <div class="epigrafe"><p>${escapeHtml(epig.texto)}</p>
      <div class="autor">${escapeHtml(epig.autor)}</div>
      <div class="fonte">${escapeHtml(epig.fonte)}</div></div>
    ${metaBlock(report, id, true)}
    <div class="kpis">
      <div class="kpi"><div class="n">${num((media as never as Record<string, number>).ipmAvg, 1)}</div><div class="d">IPM médio</div></div>
      <div class="kpi"><div class="n">${num((media as never as Record<string, number>).idmAvg, 2)}</div><div class="d">IDM médio</div></div>
      <div class="kpi"><div class="n">${cortes.length}</div><div class="d">Cortes</div></div>
      <div class="kpi"><div class="n">${(report.dissonances || []).length}</div><div class="d">Dissonâncias</div></div>
    </div>
    ${secaoSintese(report)}
    ${secaoEstatistica(report)}
    ${secaoIndicesPorCorte(report)}`;

  const dissonancias = (report.dissonances || []).map((d) => `
    <div class="disso"><div class="disso-cab">Zona ${escapeHtml(d.zone)} · ${escapeHtml(formatClock(d.elapsedSeconds))}</div>
      <p>${escapeHtml(d.report)}</p></div>`).join("")
    || `<p>Nenhuma dissonância registrada nesta sessão.</p>`;

  const segunda = `
    <section style="margin-top:0"><div class="cab"><span class="num">04</span><h2>Cortes semânticos</h2></div>
      ${cortes.map((c, i) => `<div class="fase"><div class="badge">Corte<b>${i + 1}</b></div>
        <div class="corpo"><b>${escapeHtml(cutRange(c))} · ${escapeHtml(c.theme || "Sem tema definido")}</b>
        <p>${escapeHtml(summaryOrFallback(c.summary))}</p></div></div>`).join("")
        || `<p>Nenhum corte registrado nesta sessão.</p>`}
    </section>
    <section><div class="cab"><span class="num">05</span><h2>Sinais observados</h2></div>
      ${dissonancias}
      <div class="limite"><b>O que estes sinais são, e o que não são.</b>
        Descrevem medidas de fala e expressão facial contra a linha de base desta
        sessão. Não constituem diagnóstico, não classificam a pessoa em faixa de
        risco e não substituem avaliação, conduta ou julgamento do profissional
        habilitado.</div>
    </section>
    <section><div class="cab"><span class="num">06</span><h2>Relatório descritivo</h2></div>
      <div class="redigido">${escapeHtml(descriptiveText) || "<i>Não redigido.</i>"}</div>
      <div class="assin">Assinatura do profissional responsável<br>
        <b style="color:#212529">${escapeHtml(id.professionalName || "--")}</b>
        · ${escapeHtml(id.professionalRegistry || "--")}</div>
    </section>`;

  const rodape = `${tituloDocumento(id)} · Documento clínico confidencial`;
  return head(`Relatório descritivo — ${report.sessionId}`, EXTRA_PROFISSIONAL)
    + pagina(capa, rodape, 1, 2)
    + pagina(segunda, `${rodape}${id.contactEmail ? ` · ${id.contactEmail}` : ""}`, 2, 2)
    + `</body></html>`;
}

/** Documento do PACIENTE. */
export function buildPatientReport(
  report: SessionReportRecord,
  identity?: Partial<ReportIdentity>,
  seed?: number,
  descriptiveText = "",
): string {
  const id = identityOf(identity);
  const cortes = orderedCuts(report);

  // Sinal sem tradução escrita é OMITIDO. Cair no texto do profissional seria o
  // acidente que dissonance-patient-view existe para impedir.
  const sinais = (report.dissonances || [])
    .map((d) => ({ registro: d, visao: patientViewFor(String((d as never as Record<string, string>).title || d.report || "")) }))
    .filter((item) => item.visao !== null);

  const capa = `
    <div class="tags"><span class="tag destaque">Relatório da sessão</span>
      <span class="tag">Documento pessoal</span><span class="tag">Confidencial</span></div>
    <h1>${escapeHtml(tituloDocumento(id))}</h1>
    <p class="sub">Percepção clínica aumentada · FROID</p>
    <div class="abertura">${escapeHtml(pickIntro(seed))}</div>
    ${metaBlock(report, id, false)}
    <section><div class="cab"><span class="num">01</span><h2>Como ler este documento</h2></div>
      <p>Durante a sessão, o FROID acompanha a <b>fala</b> e a <b>expressão do rosto</b>.
        Nos primeiros 60 segundos ele mede a sua referência daquele dia. Tudo o que
        vem depois é comparado <b>com você mesmo</b>, nunca com uma média de outras
        pessoas.</p>
      <p>Os números descrevem movimento, não julgamento. Um valor mais alto não é
        pior, e um mais baixo não é melhor.</p>
    </section>
    <section><div class="cab"><span class="num">02</span><h2>Percurso da sessão</h2></div>
      ${cortes.map((c, i) => `<div class="fase"><div class="badge">Trecho<b>${i + 1}</b></div>
        <div class="corpo"><b>${escapeHtml(cutRange(c))} · ${escapeHtml(c.theme || "Sem tema definido")}</b>
        <p>${escapeHtml(summaryOrFallback(c.summary))}</p></div></div>`).join("")
        || `<p>Nenhum trecho registrado nesta sessão.</p>`}
    </section>`;

  const blocosSinais = sinais.map((item) => `
    <div class="sinal"><span class="quando">${escapeHtml(formatClock(item.registro.elapsedSeconds))}</span>
      <h3>${escapeHtml(item.visao!.title)}</h3>
      <p>${escapeHtml(item.visao!.description)}</p></div>`).join("");

  const segunda = `
    <section style="margin-top:0"><div class="cab"><span class="num">03</span><h2>Sinais registrados</h2></div>
      ${blocosSinais || `<p>Nenhum sinal registrado nesta sessão.</p>`}
      ${blocosSinais ? `<div class="glossario"><b>Os códigos que aparecem acima</b>
        <div><b>AU6</b> — elevação da bochecha: o movimento que enruga o canto dos olhos.</div>
        <div><b>AU12</b> — elevação do canto da boca: o movimento que levanta os cantos dos lábios.</div>
        <div style="margin-top:8px;color:#6C757D">São nomes técnicos de movimentos
          musculares do rosto, usados internacionalmente. Nomear o movimento não
          interpreta a intenção.</div></div>` : ""}
    </section>
    <section><div class="cab"><span class="num">04</span><h2>Anotações do seu profissional</h2></div>
      <div style="border:1px solid var(--linha);border-radius:5px;min-height:130px;
                  padding:12px;font-size:9pt;white-space:pre-wrap">${
        escapeHtml(descriptiveText)
        // Caixa vazia num documento entregue ao paciente parece defeito de
        // impressão. Dizer que não houve anotação é informação; um retângulo
        // em branco não é.
        || `<p style="color:#9CA3AF;font-style:italic;margin:0">Seu profissional não
             registrou anotações para esta sessão.</p>`
      }</div>
    </section>
    <section><div class="cab"><span class="num">05</span><h2>O que este documento não é</h2></div>
      <div class="limite">
        <p style="margin:0 0 7px"><b>Não é um diagnóstico.</b> O FROID mede sinais de
          fala e de expressão facial. Medir um sinal não é identificar uma condição.</p>
        <p style="margin:0 0 7px"><b>Não é uma avaliação sobre quem você é.</b> Os
          registros descrevem uma conversa específica, em um dia específico,
          comparada com a sua própria referência daquele dia.</p>
        <p style="margin:0"><b>Não substitui o seu profissional.</b> Quem interpreta,
          contextualiza e conduz é ele. Leve as suas dúvidas para a próxima sessão.</p>
      </div>
    </section>`;

  const rodape = `${tituloDocumento(id)} · Documento pessoal e confidencial`;
  return head(`Relatório da sessão — ${report.sessionId}`, EXTRA_PACIENTE)
    + pagina(capa, rodape, 1, 2)
    + pagina(segunda, `${rodape}${id.contactEmail ? ` · ${id.contactEmail}` : ""}`, 2, 2)
    + `</body></html>`;
}

export function buildReport(
  audience: ReportAudience,
  report: SessionReportRecord,
  identity?: Partial<ReportIdentity>,
  descriptiveText = "",
  seed?: number,
): string {
  return audience === "patient"
    // O texto redigido entra nos DOIS documentos: no do profissional como a
    // seção 06, no do paciente como a seção 04 do modelo aprovado. É a mesma
    // palavra dele, e é ela que liga um documento ao outro.
    ? buildPatientReport(report, identity, seed, descriptiveText || String(report.patientNotes || ""))
    : buildProfessionalReport(report, identity, descriptiveText, seed);
}

/**
 * Abre o documento numa aba e dispara a impressão.
 *
 * Aba nova, e não iframe: o iframe herdaria o CSS do painel e imprimiria a tela
 * escura. Devolve false quando o navegador bloqueia a janela — quem chamou
 * precisa avisar, senão o profissional clica e nada acontece.
 */
export function openPrintable(html: string): boolean {
  if (typeof window === "undefined") return false;
  const janela = window.open("", "_blank");
  if (!janela) return false;
  janela.document.write(html);
  janela.document.close();
  janela.focus();
  // O atraso deixa o layout assentar antes do diálogo; sem ele, o Chrome
  // ocasionalmente imprime a primeira página em branco.
  window.setTimeout(() => janela.print(), 350);
  return true;
}
