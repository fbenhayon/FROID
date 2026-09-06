import type { SessionReportRecord } from "./session-report";
import { patientViewFor } from "./dissonance-patient-view";
import { pickEpigraph } from "./report-epigraph";
import { pickIntro } from "./report-intro";
// Faixa da marca. Vira data URI na build por assetsInlineLimit, em
// vite.config.mjs — o porque esta comentado la.
import FAIXA from "../assets/relatorio-logo.jpeg";

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

/** Chaves dos blocos que o profissional pode marcar para o documento do paciente.
 *
 *  Espelha PATIENT_REPORT_ITEMS em froid-server/main.py, e a ordem é a mesma —
 *  é ela que define a ordem das seções no documento. O catálogo com os rótulos
 *  continua vindo do servidor para a tela desenhar; aqui só as chaves, porque o
 *  gerador precisa delas para decidir o que entra mesmo quando roda sem rede,
 *  a partir de um registro já liberado.
 */
export const PATIENT_ITEM_KEYS = [
  "baseline",
  "sessionAverage",
  "sessionSummary",
  "conversationSummaries",
  "tenMinuteCuts",
  "dissonances",
  "clinicalNotes",
  "professionalNotes",
] as const;

/** Itens que levam MEDIDA ao documento — número, tabela, comparação.
 *
 *  "Como ler este documento" existe para dar a régua desses números: os 60 s de
 *  calibração, a comparação com a própria pessoa e nunca com média populacional.
 *  Num documento composto só de texto ela explicaria números que não estão lá,
 *  e vira ruído. Por isso ela é condicional, e esta é a condição. */
const ITENS_COM_MEDIDA = [
  "baseline",
  "sessionAverage",
  "conversationSummaries", // cada trecho leva ritmo, tom e zona
  "tenMinuteCuts",
];

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

/** Houve medida? `null` e `undefined` NÃO são medida.
 *
 *  `Number(null)` vale **zero**, e zero é finito. Então todo teste escrito como
 *  `Number.isFinite(Number(x))` respondia "sim, tem medida" para um campo
 *  ausente — e as onze ocorrências deste arquivo respondiam assim.
 *
 *  Enquanto `ipmAvg`, `idmAvg`, `wordsPerMinute` e `dissonanceCount` chegavam
 *  sempre como número (a origem fechava a ausência com `|| 0`), a armadilha
 *  ficava dormente: o zero vinha de lá, não daqui. Ao passar esses campos a
 *  `number | null` — que é o certo, e é o que o servidor já grava — ela
 *  acordaria toda de uma vez, e "0,0" voltaria a sair no documento do paciente
 *  pela porta ao lado. Corrigido junto, e não depois.
 */
function houveMedida(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  return Number.isFinite(Number(value));
}

function num(value: unknown, digits = 2): string {
  if (!houveMedida(value)) return "--";
  return Number(value).toFixed(digits).replace(".", ",");
}

/** O que se imprime quando NAO houve medida.
 *
 *  `0,00` era o que saia antes, e e a pior saida possivel: e finito, alinha na
 *  coluna decimal e tem duas casas — tipograficamente indistinguivel de uma
 *  medida real de zero. Num relatorio com vinte e uma linhas em `0,00`, o
 *  paciente conclui uma de duas coisas: que ficou mudo por onze minutos, ou que
 *  o aparelho nao funciona. A segunda e a correta, e e a pior das duas.
 *
 *  A ausencia chegava ate aqui como zero porque `_safe_float` no servidor tem
 *  `default=0.0`: o motor de metricas devolve `None` com honestidade e a
 *  gravacao converte. Aqui a distincao volta pela PROCEDENCIA, que e afirmacao
 *  registrada — nao por adivinhar que zero significa ausencia, que seria trocar
 *  uma suposicao por outra. */
const NAO_MEDIDO = '<span class="ausente">não medido nesta sessão</span>';
const NAO_REGISTRADO = '<span class="ausente">não registrado</span>';

/** Numero que so aparece se houve apuracao.
 *
 *  `apurado`: `true` medido, `false` sem capacidade de apuracao, `null` para
 *  relatorio anterior ao registro de procedencia — onde nao da para afirmar nem
 *  uma coisa nem outra, e dizer "nao registrado" e a unica leitura honesta. */
function medida(value: unknown, digits: number, apurado: boolean | null): string {
  if (apurado === false) return NAO_MEDIDO;
  // Campo NULO é ausência declarada pela origem, e não valor ilegível: desde
  // que o construtor de cortes parou de fechar a lacuna com zero, `null` aqui
  // significa exatamente "não houve apuração nesta janela". Sem esta linha,
  // `Number(null)` viraria `0` e imprimiria "0,0" — o `0,00` que este arquivo
  // inteiro existe para não repetir, entrando pela porta ao lado.
  if (value === null || value === undefined) return NAO_MEDIDO;
  const n = Number(value);
  if (!Number.isFinite(n)) return NAO_REGISTRADO;
  return n.toFixed(digits).replace(".", ",");
}

/** So a TESE do resumo, para o documento do paciente.
 *
 *  `buildSessionSummary` monta o resumo em tres partes: a tese, a recomposicao
 *  de todos os cortes, e uma frase de maquina sobre como o resumo deve ser
 *  lido. Num relatorio real de 04/09/2026 a parte do meio reproduziu, palavra
 *  por palavra, os tres cortes que a secao seguinte ja mostra — o paciente lia
 *  a mesma conversa duas vezes seguidas, e a segunda em paragrafo corrido.
 *
 *  O corte e feito por um literal do NOSSO proprio gabarito, nao por heuristica
 *  sobre texto de modelo: se o gabarito mudar, o `indexOf` falha, e a funcao
 *  devolve o texto inteiro — que e o comportamento de hoje. Degrada para o
 *  estado anterior em vez de degradar para vazio. */
export function teseDaSessao(texto: string): string {
  const marca = texto.indexOf("A sequência dos cortes indica");
  if (marca <= 0) return texto;
  return texto.slice(0, marca).trim();
}

/** A pergunta que fecha cada trecho.
 *
 *  Ela existe para causar o que o Fabio formulou: devolver o paciente ao
 *  assunto antes da proxima sessao, em vez de lhe entregar uma conclusao
 *  pronta. Por isso e pergunta e nao afirmacao, e por isso sai sempre de um
 *  numero MEDIDO — quanto tempo o trecho ocupou, ou de quanto para quanto o
 *  ritmo mudou.
 *
 *  Nenhuma delas interpreta o conteudo. "Voce estava ansioso aqui" seria
 *  diagnostico tirado de um proxy; "a sua fala acelerou 36% aqui" e o registro
 *  do que aconteceu, e a leitura fica com quem viveu a conversa. */
function perguntaDoTrecho(dados: {
  ritmo: number | null;
  ritmoAnterior: number | null;
  ehMaisLongo: boolean;
  fatia: number;
}): string {
  const { ritmo, ritmoAnterior, ehMaisLongo, fatia } = dados;
  const pct =
    ritmo !== null && ritmoAnterior !== null && ritmoAnterior > 0
      ? Math.round(((ritmo - ritmoAnterior) / ritmoAnterior) * 100)
      : null;

  // A mudanca de ritmo vem antes do tamanho: e a mais especifica das duas, e a
  // que o paciente tem menos chance de ter percebido sozinho.
  if (pct !== null && Math.abs(pct) >= 12) {
    const verbo = pct > 0 ? "acelerou" : "desacelerou";
    return `<p class="pergunta"><b>Para pensar:</b> aqui a sua fala ${verbo} de
      ${num(ritmoAnterior, 0)} para ${num(ritmo, 0)} palavras por minuto.
      Você percebeu essa mudança enquanto falava?</p>`;
  }
  if (ehMaisLongo && fatia > 0) {
    return `<p class="pergunta"><b>Para pensar:</b> este foi o trecho mais longo
      da conversa — ${fatia}% do tempo. O que faz este assunto ocupar tanto
      espaço?</p>`;
  }
  return `<p class="pergunta"><b>Para pensar:</b> o que deste trecho você
    gostaria de retomar na próxima sessão?</p>`;
}

/** Duracao de um corte pelo relogio real, e nao pelo minuto arredondado.
 *
 *  A diferenca nao e cosmetica: nesta sessao os rotulos redondos produziram
 *  "0-4min" e "3-4min" para cortes de 3min37 e 12 SEGUNDOS, que assim parecem
 *  do mesmo tamanho. */
function cutSeconds(cut: Record<string, unknown>): number {
  const inicio = Number(cut.startSecond ?? Number(cut.startMinute) * 60);
  const fim = Number(cut.endSecond ?? Number(cut.endMinute) * 60);
  if (!Number.isFinite(inicio) || !Number.isFinite(fim)) return 0;
  return Math.max(0, fim - inicio);
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
/* A folha tem altura FIXA e é uma coluna: faixa, conteúdo, rodapé. O conteúdo
   é o único elemento elástico, e é a altura dele que o paginador mede para
   decidir onde a folha acaba. Com min-height o navegador esticaria a folha em
   vez de acusar o excesso, e a medição perderia o sentido. */
.folha{width:210mm;height:297mm;margin:0 auto;padding:0 14mm 12mm;
       display:flex;flex-direction:column;overflow:hidden;
       position:relative;page-break-after:always;background:#fff}
.folha:last-child{page-break-after:auto}
.conteudo{flex:1;min-height:0;overflow:hidden;padding-top:9mm}
.bloco{break-inside:avoid}
/* Faixa da marca, sangrando até as bordas laterais da folha. */
/* A altura vem do paginador, calculada da proporção real da imagem — ver a
   regra que ele injeta. Aqui fica só o que não depende dela. */
.cabecalho{margin:0 -14mm;position:relative;flex:0 0 auto;
           background-repeat:no-repeat;background-size:100% 100%}
.cabecalho .prof{position:absolute;right:14mm;bottom:3mm;font-size:7.5pt;
                 font-weight:700;letter-spacing:.04em;color:#E2E8F0;
                 max-width:45%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
                 text-shadow:0 1px 3px rgba(0,0,0,.85)}
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
.bloco:first-child section:first-child{margin-top:0}
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
/* Parágrafo de texto livre: cada um é um bloco para o paginador, então a
   margem entre eles vive aqui e não em margin-bottom acumulado. */
.corrido{margin:0 0 8px;font-size:9pt;line-height:1.6;white-space:pre-wrap}
.fase .numeros{margin-top:4px;font-size:7.5pt;color:var(--rotulo);letter-spacing:.02em}
.fase .zona{margin-top:6px;background:var(--fundo);border-left:2px solid var(--azul);
            padding:6px 9px;border-radius:0 4px 4px 0;font-size:8pt}
.limite{background:#451A03;border:1px solid #92400E;border-radius:6px;padding:11px 13px;
        font-size:8.5pt;color:#FDE68A;margin-top:12px;line-height:1.55}
.limite b{color:#FCD34D}
footer{flex:0 0 auto;margin-top:8px;padding-top:7px;border-top:1px solid var(--linha);
       display:flex;justify-content:space-between;gap:12px;color:var(--rotulo);font-size:7pt}
footer .quem{font-weight:700;color:var(--navy)}
/* Cabeçalho repetido em toda folha: marca à esquerda, profissional à direita.
   Fica sobre a faixa colorida, por isso o texto é claro. */

/* IMPRESSÃO
   print-color-adjust é o que decide se este documento sai colorido ou em
   branco. Por padrão o navegador descarta cor de fundo ao imprimir — some a
   faixa do topo, somem os cabeçalhos navy das tabelas e somem os selos de
   alerta, que passam a ser texto cinza sobre branco. Num relatório em que a
   cor CARREGA significado (verde/âmbar/vermelho por métrica), perder o fundo
   não é perder estética: é perder informação. */
@media print{
  html,body{background:#fff}
  body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .folha{margin:0;box-shadow:none;page-break-after:always}
  .folha:last-child{page-break-after:auto}
  section{break-inside:auto}
  .fase,.disso,.sinal,tr{break-inside:avoid}
  thead{display:table-header-group}
}
@page{size:A4;margin:0}
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
.continua{font-size:7pt;color:var(--rotulo);margin:0 0 3px;font-style:italic;
          text-transform:uppercase;letter-spacing:.06em}
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
.ausente{color:#9AA1A9;font-style:italic}
.peso{border:1px solid var(--linha);border-left:3px solid var(--azul);
      border-radius:0 6px 6px 0;padding:12px 14px;margin:11px 0;page-break-inside:avoid}
.peso dt{color:var(--rotulo);font-size:7.5pt;font-weight:700;text-transform:uppercase;
         letter-spacing:.04em;margin:0 0 2px}
.peso dd{margin:0 0 10px;font-size:10pt;color:var(--navy)}
.peso dd:last-child{margin-bottom:0}
.pergunta{background:var(--fundo);border-radius:5px;padding:8px 10px;margin:8px 0 0;
          font-size:8.5pt;color:var(--navy)}
.pergunta b{color:var(--azul)}
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

/** Título do documento do PACIENTE: o nome de quem o recebe.
 *
 *  A capa trazia a clínica ou o profissional, os mesmos que o bloco de
 *  identificação logo abaixo já nomeia em "Profissional" e "Registro" — e o
 *  destaque da folha ficava com quem não é o destinatário dela. Sem nome no
 *  registro, cai no rótulo genérico: nunca no do profissional, que é
 *  justamente o que este título deixou de ser. */
function tituloDoPaciente(report: SessionReportRecord): string {
  return String(report.patientName || report.patient?.name || "").trim()
    || "Relatório da sessão";
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
      ${id.professionalRegistry ? `<dt>Registro</dt><dd>${escapeHtml(id.professionalRegistry)}</dd>` : ""}
      <dt>Data da sessão</dt><dd>${escapeHtml(sessionDate(report))}</dd>
    </div><div>
      ${mostraPaciente
        ? `<dt>Paciente</dt><dd>${escapeHtml(report.patientName || report.patient?.name || "--")}</dd>`
        : ""}
      <dt>Sessão</dt><dd>${escapeHtml(report.sessionId)}</dd>
      <dt>Duração</dt><dd>${escapeHtml(formatDurationLong(report.durationSeconds))}</dd>
    </div></div>`;
}

/** Monta o documento e o pagina MEDINDO, no navegador, antes de imprimir.
 *
 *  A versão anterior repartia por contagem — quatro cortes por folha, cinco
 *  blocos por folha — e o resultado foi meia página em branco em quase toda
 *  folha: o limite tinha de ser conservador para o pior caso, então no caso
 *  comum sobrava papel. Documento clínico com metade da página vazia não
 *  parece cauteloso, parece malfeito.
 *
 *  Contar blocos nunca ia funcionar, porque a altura de um bloco depende do
 *  texto dentro dele, e o texto vem da sessão. A única medida honesta é a
 *  altura real, e quem sabe dela é o navegador. Então o documento sai como uma
 *  lista de blocos e um script que, ao abrir, enche cada folha até o limite do
 *  papel e só então começa a próxima.
 *
 *  O script roda na janela do relatório, antes do print — openPrintable espera
 *  350 ms justamente porque a impressão precisa do layout já resolvido.
 */
function documento(
  blocos: string[],
  rodape: string,
  rodapeFim: string,
  quem: string,
): string {
  // A faixa NÃO vai como <img> por folha. Ia: e num documento de 35 folhas isso
  // colocava 35 cópias do mesmo data URI de 92 KB dentro do documento, que a
  // impressão depois precisa rasterizar uma por uma. Agora ela é fundo de
  // .cabecalho, declarado UMA vez numa regra de estilo que o paginador insere.
  const cabecalho =
    `<div class="cabecalho">`
    + (quem ? `<span class="prof">${escapeHtml(quem)}</span>` : "")
    + `</div>`;

  // Rodapé vai para innerHTML dentro do paginador, então escapa AQUI. A versão
  // com folhas fixas escapava dentro de pagina(); ao trocar o caminho eu tinha
  // deixado o texto passar cru, e nome de clínica com marcação injetaria HTML
  // no documento impresso.
  return `<div id="fluxo">${blocos.map((b) => `<div class="bloco">${b}</div>`).join("")}</div>`
    + `<script>(${paginador.toString()})(${JSON.stringify({
      cabecalho,
      rodape: escapeHtml(rodape),
      rodapeFim: escapeHtml(rodapeFim),
      faixa: FAIXA,
    })});<\/script>`;
}

/** Executa DENTRO da janela do relatório. Não pode referenciar nada do módulo:
 *  vai serializada por toString(). */
function paginador(cfg: { cabecalho: string; rodape: string; rodapeFim: string; faixa: string }) {
  // ESPERA A FAIXA CARREGAR ANTES DE MEDIR. Sem isto o paginador mede com a
  // imagem ainda sem decodificar, ocupando altura zero: sobra espaço aparente,
  // ele enfia um bloco a mais, e quando a faixa aparece o excesso é cortado
  // por overflow:hidden. Foi medido — 14 a 33 px sumindo por folha.
  var pre = new Image();
  pre.onload = paginar;
  pre.onerror = paginar; // faixa quebrada não pode impedir o documento
  pre.src = cfg.faixa;
  if (pre.complete) paginar();

  /** Regra única da faixa, com a altura tirada da proporção real da imagem.
   *
   *  Calcular em vez de fixar deixa a faixa correta se o arquivo for trocado
   *  por outro de proporção diferente — e é justamente o arquivo que o dono do
   *  produto troca sem mexer em código.
   */
  function instalarFaixa() {
    var mm = pre.naturalWidth ? (210 * pre.naturalHeight) / pre.naturalWidth : 15;
    var est = document.createElement("style");
    est.textContent = ".cabecalho{height:" + (Math.round(mm * 100) / 100) + "mm"
      + (pre.naturalWidth ? ';background-image:url("' + cfg.faixa + '")' : "")
      + "}";
    document.head.appendChild(est);
  }

  var jaRodou = false;
  function paginar() {
    if (jaRodou) return;
    jaRodou = true;

    // A faixa entra ANTES de medir: ela define a altura do cabeçalho, e medir
    // sem ela faria sobrar espaço aparente em toda folha.
    instalarFaixa();

    var fluxo = document.getElementById("fluxo");
    if (!fluxo) return;
    var ancora = fluxo.parentNode as Node;
    var blocos: Element[] = [];
    while (fluxo.firstElementChild) blocos.push(fluxo.removeChild(fluxo.firstElementChild));

    var folhas: HTMLElement[] = [];
    function novaFolha() {
      // Teto de segurança. Nenhum documento clínico real chega perto disto; se
      // chegar, é defeito, e defeito não pode travar a máquina de quem está em
      // atendimento. Melhor documento truncado do que aba morta.
      if (folhas.length >= 300) return corpoDe(folhas.length - 1);
      var folha = document.createElement("div");
      folha.className = "folha";
      // O rodapé nasce com o texto MAIS LONGO dos dois, e não vazio: numerar
      // depois faria o rodapé crescer e encolher o conteúdo já medido.
      folha.innerHTML = cfg.cabecalho
        + '<div class="conteudo"></div>'
        + '<footer><span class="esq">' + cfg.rodapeFim
        + '</span><span class="dir">Página 00 de 00</span></footer>';
      // O #fluxo é a âncora enquanto existe; na passagem de acerto ele já foi
      // removido, e aí a folha nova vai para o fim — que é onde ela pertence,
      // porque só se cria folha nova a partir da última.
      if (fluxo!.parentNode === ancora) ancora.insertBefore(folha, fluxo);
      else ancora.appendChild(folha);
      folhas.push(folha);
      return folha.querySelector(".conteudo") as HTMLElement;
    }
    function corpoDe(i: number) {
      return folhas[i].querySelector(".conteudo") as HTMLElement;
    }
    /** Parte a tabela do bloco que acabou de estourar a folha.
     *
     *  Sem isto uma tabela cabe inteira ou salta para a folha seguinte, e o
     *  vão que ela deixa atrás pode ser um terço de página. Aqui as linhas do
     *  fim voltam para um bloco de continuação, que herda o MESMO thead — sem
     *  ele a continuação seria uma parede de números sem dizer o que é cada
     *  coluna, o que é pior do que o vão.
     *
     *  Devolve o bloco de continuação, ou null quando não há o que partir:
     *  bloco sem tabela, ou tabela que já está na última linha.
     */
    function partirTabela(bloco: Element): Element | null {
      var tabela = bloco.querySelector("table");
      if (!tabela) return null;
      var tbody = tabela.tBodies[0];
      if (!tbody || tbody.rows.length < 2) return null;

      var removidas: HTMLTableRowElement[] = [];
      // Deixa ao menos uma linha para trás: cabeçalho de tabela seguido de nada
      // não é tabela, é enfeite.
      while (cheio(bloco.parentElement as HTMLElement) && tbody.rows.length > 1) {
        removidas.unshift(tbody.rows[tbody.rows.length - 1]);
        tbody.deleteRow(tbody.rows.length - 1);
      }
      if (!removidas.length) return null;

      var cont = document.createElement("div");
      cont.className = "bloco";
      // Diz que é continuação. Sem isso a folha seguinte abre com uma tabela
      // sem título, e o leitor não sabe se é a mesma ou outra.
      var aviso = document.createElement("p");
      aviso.className = "continua";
      aviso.textContent = "continuação da tabela anterior";
      cont.appendChild(aviso);
      var tabCont = tabela.cloneNode(false) as HTMLTableElement;
      if (tabela.tHead) {
        var chefe = tabela.tHead.cloneNode(true) as HTMLTableSectionElement;
        // Copia a largura MEDIDA de cada coluna e fixa o layout. Sem isso cada
        // parte da tabela se auto-dimensiona pelo próprio conteúdo, e as
        // colunas dançam de uma folha para a outra — o leitor perde a referência
        // do que está lendo.
        var origem = tabela.tHead.rows[0];
        var destino = chefe.rows[0];
        if (origem && destino) {
          for (var col = 0; col < destino.cells.length; col++) {
            if (origem.cells[col]) {
              destino.cells[col].style.width = origem.cells[col].offsetWidth + "px";
            }
          }
          tabCont.style.tableLayout = "fixed";
        }
        tabCont.appendChild(chefe);
      }
      var tbCont = document.createElement("tbody");
      for (var r = 0; r < removidas.length; r++) tbCont.appendChild(removidas[r]);
      tabCont.appendChild(tbCont);
      cont.appendChild(tabCont);
      return cont;
    }

    /** Última rede contra corte: um bloco que não cabe nem sozinho e tem filhos
     *  devolve os últimos filhos para um bloco de continuação.
     *
     *  Serve para texto que passa de uma folha inteira. O caso comum já não
     *  chega aqui — texto livre entra como um bloco por parágrafo —, mas um
     *  parágrafo único gigantesco, colado de outro sistema, chegaria. Sem isto
     *  ele seria cortado por overflow:hidden, em silêncio.
     */
    function partirTexto(bloco: Element): Element | null {
      var alvo = bloco.parentElement as HTMLElement;

      // Caso comum: vários filhos. Devolve os últimos.
      if (bloco.children.length > 1) {
        var removidos: Element[] = [];
        while (cheio(alvo) && bloco.children.length > 1) {
          removidos.unshift(bloco.removeChild(bloco.lastElementChild!));
        }
        if (removidos.length) {
          var cont = document.createElement("div");
          cont.className = "bloco";
          for (var k = 0; k < removidos.length; k++) cont.appendChild(removidos[k]);
          return cont;
        }
        return null;
      }

      // UM parágrafo maior que a folha inteira. Acontece com texto colado de
      // outro sistema, sem linha em branco: 900 palavras num bloco só. Não há
      // filho para mover, então parte por PALAVRA. Sem isto o excesso é cortado
      // por overflow:hidden e o paciente recebe a anotação truncada no meio de
      // uma frase, sem nada indicando que falta texto.
      var alvoP = bloco.children.length === 1 ? bloco.firstElementChild! : bloco;

      // SÓ PARÁGRAFO DE TEXTO PURO. Escrever textContent num elemento com
      // estrutura dentro apaga a marcação: foi assim que o bloco da advertência
      // saiu como texto corrido, sem a caixa âmbar, sem o título e truncado no
      // meio de uma frase. Se há filho elemento, este não é um parágrafo — é uma
      // seção, e seção não se parte por palavra.
      if (alvoP.children.length > 0) return null;

      var palavras = String(alvoP.textContent || "").split(/\s+/).filter(Boolean);
      if (palavras.length < 20) return null;

      var sobra: string[] = [];
      var guarda = 0;
      // Passo de 5% por vez: palavra a palavra seriam centenas de reflows.
      var passo = Math.max(1, Math.floor(palavras.length / 20));
      while (cheio(alvo) && palavras.length > 10 && guarda++ < 200) {
        for (var t = 0; t < passo && palavras.length > 10; t++) {
          sobra.unshift(palavras.pop() as string);
        }
        alvoP.textContent = palavras.join(" ");
      }
      if (!sobra.length) return null;

      var contP = document.createElement("div");
      contP.className = "bloco";
      var par = document.createElement("p");
      par.className = alvoP.className || "corrido";
      par.textContent = sobra.join(" ");
      contP.appendChild(par);
      return contP;
    }

    function cheio(c: HTMLElement) {
      // overflow:hidden nunca reporta scrollHeight abaixo de clientHeight, então
      // a folga tem de ser POSITIVA. Com folga negativa o teste dá verdadeiro
      // sempre e sai uma folha por bloco.
      return c.scrollHeight > c.clientHeight + 1;
    }

    var corpo = novaFolha();
    for (var i = 0; i < blocos.length; i++) {
      corpo.appendChild(blocos[i]);
      if (!cheio(corpo)) continue;

      // Tabela é o primeiro recurso: partir custa menos vão do que mover.
      var cont = partirTabela(blocos[i]) || partirTexto(blocos[i]);
      if (cont) {
        blocos.splice(i + 1, 0, cont);
        // Folha nova para a continuação. Devolvê-la à folha atual, que acabou de
        // encher, fazia a tabela partir outra vez — e outra — até sair uma
        // linha por tabelinha, cada uma com o seu cabeçalho.
        corpo = novaFolha();
        continue;
      }
      // Não é tabela: o bloco inteiro vai para a folha seguinte. Só não vai se
      // for o único da folha — nesse caso ele fica e transborda, que é melhor
      // do que entrar em laço.
      if (corpo.children.length > 1) {
        corpo.removeChild(blocos[i]);
        corpo = novaFolha();
        corpo.appendChild(blocos[i]);
      }
    }
    ancora.removeChild(fluxo);

    // PASSAGEM DE ACERTO. A medição durante a montagem pode ficar defasada por
    // qualquer coisa que mude altura depois — fonte que termina de carregar,
    // imagem, ajuste de layout. Aqui se confere folha por folha o que de fato
    // ficou e empurra o excedente adiante, até estabilizar. É a rede que
    // garante que nada seja cortado, independentemente do que atrasou.
    for (var f = 0; f < folhas.length; f++) {
      var guarda = 0;
      while (cheio(corpoDe(f)) && corpoDe(f).children.length > 1 && guarda++ < 100) {
        var ultimo = corpoDe(f).lastElementChild!;
        if (f === folhas.length - 1) novaFolha();
        var seguinte = corpoDe(f + 1);
        // Aqui também: parte a tabela antes de empurrar o bloco todo.
        var resto = partirTabela(ultimo) || partirTexto(ultimo);
        if (resto) {
          seguinte.insertBefore(resto, seguinte.firstChild);
          continue;
        }
        seguinte.insertBefore(ultimo, seguinte.firstChild);
      }
    }

    // Só agora: encurtar o rodapé das folhas que não são a última e escrever a
    // numeração real. As duas trocas só reduzem altura.
    for (var g = 0; g < folhas.length; g++) {
      var esq = folhas[g].querySelector(".esq") as HTMLElement;
      var dir = folhas[g].querySelector(".dir") as HTMLElement;
      if (g !== folhas.length - 1) esq.innerHTML = cfg.rodape;
      dir.textContent = "Página " + (g + 1) + " de " + folhas.length;
    }

    // A IMPRESSÃO SÓ AGORA. Antes ela era disparada por um temporizador de
    // 350 ms em openPrintable, e este paginador é assíncrono: espera a imagem
    // carregar e só então remonta o documento. Num documento longo o diálogo de
    // impressão abria com a remontagem em curso — imprimir enquanto o DOM muda
    // sob o motor de layout é como o sistema travava.
    (window as unknown as Record<string, unknown>).__froidPaginado = true;
    window.setTimeout(function () { window.print(); }, 60);
  }
}

/** Quebra texto livre em blocos de parágrafo, um por bloco.
 *
 *  Texto do profissional entrava como UM bloco só, e bloco é indivisível para o
 *  paginador: ele não descia para preencher o espaço livre da folha anterior, e
 *  quando passava de uma folha o excesso era CORTADO — medido em 154% de
 *  ocupação, mais da metade da anotação perdida em silêncio. Texto tem de fluir
 *  como texto flui.
 *
 *  Separa por linha em branco, que é como se escreve parágrafo. Quebra simples
 *  dentro do parágrafo é preservada pelo white-space do CSS.
 */
function blocosDeTexto(texto: string): string[] {
  return String(texto || "")
    .split(/\n\s*\n/)
    .map((par) => par.trim())
    .filter(Boolean)
    .map((par) => `<p class="corrido">${escapeHtml(par)}</p>`);
}

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
    // Corte sem fala do paciente apurada sai da lista, em vez de entrar como
    // "0,0" — a enumeração de ritmos passaria a incluir um valor que ninguém
    // mediu, no meio de valores medidos, sem nada distinguindo os dois.
    .filter(houveMedida)
    .map((v) => num(v, 1));

  const temas = cortes.map((c) => String((c as unknown as Record<string, unknown>).theme || "")).filter(Boolean);
  // Enumerar todos os temas era duplamente ruim: uma sessão longa produzia um
  // parágrafo com vinte e quatro itens separados por ponto e vírgula, ilegível,
  // e o bloco crescia além da folha inteira. Os primeiros seis dizem a
  // direção; o resto está listado corte a corte na seção 04, com intervalo e
  // resumo, que é onde se procura o detalhe.
  const TEMAS_NA_SINTESE = 6;
  const temasMostrados = temas.slice(0, TEMAS_NA_SINTESE);
  const restantes = temas.length - temasMostrados.length;
  const progressao = temas.length
    ? `A sequência dos cortes indica substância central organizada em torno de `
      + `${escapeHtml(temasMostrados.join("; "))}`
      + (restantes > 0
        ? `, e outros ${restantes} ${restantes === 1 ? "tema" : "temas"} detalhados na seção 04.`
        : ".")
    : "Não há cortes com tema registrado nesta sessão.";

  const linhaIndices = [
    houveMedida(media.ipmAvg) ? `IPM médio ${num(media.ipmAvg, 1)}` : "",
    houveMedida(media.idmAvg) ? `IDM médio ${num(media.idmAvg, 2)}` : "",
    ritmos.length ? `ritmo de fala ${ritmos.join(" → ")} palavras por minuto` : "",
  ].filter(Boolean).join(" · ");

  const notaBase = [
    houveMedida(base.ipmAvg) ? `IPM ${num(base.ipmAvg, 2)}` : "",
    houveMedida(base.idmAvg) ? `IDM ${num(base.idmAvg, 2)}` : "",
    base.dominantZone !== undefined && base.dominantZone !== null ? `Zona ${escapeHtml(base.dominantZone)}` : "",
    houveMedida(base.wordsPerMinute) ? `${num(base.wordsPerMinute, 1)} palavras/min` : "",
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
function secaoEstatistica(report: SessionReportRecord): string[] {
  const analise = report.metricsAnalysis;
  if (!analise || !Array.isArray(analise.metrics) || !analise.metrics.length) {
    return [`<section><div class="cab"><span class="num">02</span><h2>Leitura estatística</h2></div>
      <p>${escapeHtml(
        report.metricsAnalysisError
          || "A análise estatística não está disponível para esta sessão.",
      )}</p></section>`];
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

  // Dois blocos, e a separação tem razão: a tabela pode ser partida entre
  // folhas, e a linha de cobertura resume TODAS as linhas. Se ela viesse dentro
  // do mesmo bloco, ficaria na folha da primeira metade, resumindo números que
  // só aparecem na folha seguinte.
  return [
    `<section><div class="cab"><span class="num">02</span><h2>Leitura estatística</h2></div>
      <table>
        <thead><tr>
          <th>Métrica</th><th class="n">Baseline</th><th class="n">Média</th>
          <th class="n">Último corte</th><th class="n">Delta</th><th>Alerta</th>
        </tr></thead>
        <tbody>${linhas}</tbody>
      </table>
    </section>`,
    ...(cobertura ? [`<p class="cobertura">${escapeHtml(cobertura)}.</p>`] : []),
  ];
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
      <td class="n">${num(r.dissonanceCount, 0)}</td></tr>`;
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
  `;

  // A síntese é bloco próprio: junto da capa, numa sessão longa, o conjunto
  // passava da folha inteira e o excedente era cortado — bloco que não cabe
  // sozinho não tem para onde ir.
  const sintese = secaoSintese(report);

  const tabelas = [...secaoEstatistica(report), secaoIndicesPorCorte(report)];

  // O cabeçalho da seção vai num bloco, e cada corte no seu. O paginador
  // preenche a folha até o papel acabar; se a seção não couber inteira, ela
  // continua na folha seguinte, sem deixar página pela metade.
  const blocoCortes = [
    `<section><div class="cab"><span class="num">04</span><h2>Cortes semânticos</h2></div></section>`,
    ...(cortes.length
      ? cortes.map((c, i) => `<div class="fase"><div class="badge">Corte<b>${i + 1}</b></div>
          <div class="corpo"><b>${escapeHtml(cutRange(c))} · ${escapeHtml(c.theme || "Sem tema definido")}</b>
          <p>${escapeHtml(summaryOrFallback(c.summary))}</p></div></div>`)
      : [`<p>Nenhum corte registrado nesta sessão.</p>`]),
  ];

  // Blocos finos: cada sinal é seu próprio bloco, então a seção preenche a
  // folha e continua na seguinte em vez de saltar inteira e deixar meia página
  // vazia — que era a queixa.
  const blocoSinais = [
    `<section><div class="cab"><span class="num">05</span><h2>Sinais observados</h2></div></section>`,
    ...((report.dissonances || []).length
      ? (report.dissonances || []).map((d) => `
        <div class="disso"><div class="disso-cab">Zona ${escapeHtml(d.zone)} · ${escapeHtml(formatClock(d.elapsedSeconds))}</div>
          <p>${escapeHtml(d.report)}</p></div>`)
      : [`<p>Nenhuma dissonância registrada nesta sessão.</p>`]),
    `<div class="limite"><b>O que estes sinais são, e o que não são.</b>
      Descrevem medidas de fala e expressão facial contra a linha de base desta
      sessão. Não constituem diagnóstico, não classificam a pessoa em faixa de
      risco e não substituem avaliação, conduta ou julgamento do profissional
      habilitado.</div>`,
  ];

  // A assinatura NÃO se separa do texto que ela assina: os dois vão no mesmo
  // bloco, para que o paginador nunca os ponha em folhas diferentes.
  const blocoDescritivo = [
    `<section><div class="cab"><span class="num">06</span><h2>Relatório descritivo</h2></div>
      <div class="redigido">${escapeHtml(descriptiveText) || "<i>Não redigido.</i>"}</div>
      <div class="assin">Assinatura do profissional responsável<br>
        <b style="color:#212529">${escapeHtml(id.professionalName || "--")}</b>
        · ${escapeHtml(id.professionalRegistry || "--")}</div>
    </section>`,
  ];

  const rodape = `${tituloDocumento(id)} · Documento clínico confidencial`;
  const rodapeFim = `${rodape}${id.contactEmail ? ` · ${id.contactEmail}` : ""}`;
  return head(`Relatório descritivo — ${report.sessionId}`, EXTRA_PROFISSIONAL)
    + documento(
      [capa, sintese, ...tabelas, ...blocoCortes, ...blocoSinais, ...blocoDescritivo],
      rodape, rodapeFim, id.professionalName,
    )
    + `</body></html>`;
}

/** Documento do PACIENTE. */
export function buildPatientReport(
  report: SessionReportRecord,
  identity?: Partial<ReportIdentity>,
  seed?: number,
  descriptiveText = "",
  itens?: string[],
): string {
  const id = identityOf(identity);
  const cortes = orderedCuts(report);

  // A SELEÇÃO DO PROFISSIONAL GOVERNA O CONTEÚDO.
  //
  // Antes ela não chegava aqui: o filtro existia no servidor, para o que a área
  // do paciente recebe, mas o botão "PDF paciente" na tela do profissional
  // montava do registro completo. Resultado — marcar e desmarcar não mudava
  // nada no documento, que foi exatamente o que se viu em uso.
  //
  // Sem lista explícita, cai em patientReportItems, que é o que o servidor
  // gravou na liberação. Sem nenhum dos dois, entra tudo: um documento aberto
  // sem contexto de liberação não deve esconder o que o profissional nunca
  // pediu para esconder.
  const selecionados = (
    itens
    || (Array.isArray((report as unknown as Record<string, unknown>).patientReportItems)
      ? ((report as unknown as Record<string, unknown>).patientReportItems as string[])
      : null)
    || PATIENT_ITEM_KEYS.slice()
  );
  const tem = (chave: string) => selecionados.indexOf(chave) >= 0;
  const levaMedida = ITENS_COM_MEDIDA.some((chave) => tem(chave));

  // Sinal sem tradução escrita é OMITIDO. Cair no texto do profissional seria o
  // acidente que dissonance-patient-view existe para impedir.
  const sinais = (report.dissonances || [])
    .map((d) => ({ registro: d, visao: patientViewFor(String((d as never as Record<string, string>).title || d.report || "")) }))
    .filter((item) => item.visao !== null);

  const media = (report.sessionAverage || {}) as unknown as Record<string, unknown>;
  const base = (report.baseline || {}) as unknown as Record<string, unknown>;

  // A procedência decide se um número existe ou se a sua ausência é que existe.
  const proc = report.procedenciaDosDados;
  const vozApurada: boolean | null = proc ? proc.amostrasComVozReal > 0 : null;
  const faceApurada: boolean | null = proc ? proc.amostrasComFaceReal > 0 : null;
  const semVoz = vozApurada === false;

  // Numeração corrida, atribuída na ordem em que as seções realmente entram.
  // Fixar 01..05 quebraria o documento assim que uma seção fosse desmarcada:
  // sairia "01, 03, 05", que lê como se faltassem páginas.
  let n = 0;
  const numero = () => String(++n).padStart(2, "0");
  const cab = (titulo: string) =>
    `<div class="cab"><span class="num">${numero()}</span><h2>${escapeHtml(titulo)}</h2></div>`;

  const capa = `
    <div class="tags"><span class="tag destaque">Relatório da sessão</span>
      <span class="tag">Documento pessoal</span><span class="tag">Confidencial</span></div>
    <h1>${escapeHtml(tituloDoPaciente(report))}</h1>
    <p class="sub">Percepção clínica aumentada · FROID</p>
    <div class="abertura">${escapeHtml(pickIntro(seed))}</div>
    ${metaBlock(report, id, false)}
    ${levaMedida ? `<section>${cab("Como ler este documento")}
      <p>Durante a sessão, o FROID acompanha a <b>fala</b> e a <b>expressão do rosto</b>.
        Nos primeiros 60 segundos ele mede a sua referência daquele dia. Tudo o que
        vem depois é comparado <b>com você mesmo</b>, nunca com uma média de outras
        pessoas.</p>
      <p>Os números descrevem movimento, não julgamento. Um valor mais alto não é
        pior, e um mais baixo não é melhor.</p>
    </section>` : ""}
  `;

  const blocos: string[] = [capa];

  // ---- o que mais pesou: as duas leituras que NAO dependem de medir ----
  //
  // Esta seção nasceu de um relatório real de 04/09/2026 em que a apuração
  // acústica não aconteceu: vinte e uma linhas em `0,00`. Mesmo ali, duas
  // coisas tinham sido medidas de verdade — quanto tempo cada assunto ocupou e
  // em que velocidade a pessoa falava dentro de cada um. As duas saem da
  // própria conversa, não do microfone, e as duas estavam no documento,
  // repartidas entre duas tabelas em corpo 8, cercadas de zeros que as
  // desmentiam.
  //
  // Ela vem antes de qualquer número de voz porque é o que sobra de pé quando
  // tudo o mais falta — e porque é a leitura que o paciente consegue
  // reconhecer sozinho, que é o ponto do documento.
  if (tem("conversationSummaries") && cortes.length) {
    const comTempo = cortes
      .map((c) => {
        const r = c as unknown as Record<string, unknown>;
        return {
          tema: String(c.theme || "Sem tema definido"),
          segundos: cutSeconds(r),
          ritmo: houveMedida(r.wordsPerMinute) ? Number(r.wordsPerMinute) : null,
        };
      })
      .filter((c) => c.segundos > 0);
    const total = comTempo.reduce((soma, c) => soma + c.segundos, 0);

    const maisLongo = comTempo.reduce(
      (maior, c) => (maior === null || c.segundos > maior.segundos ? c : maior),
      null as (typeof comTempo)[number] | null,
    );

    // A maior variação de ritmo ENTRE trechos vizinhos. Comparar com a média da
    // sessão diluiria justamente o que se quer mostrar: a virada.
    let virada: { tema: string; de: number; para: number; pct: number } | null = null;
    for (let i = 1; i < comTempo.length; i += 1) {
      const antes = comTempo[i - 1].ritmo;
      const agora = comTempo[i].ritmo;
      if (antes === null || agora === null || antes <= 0) continue;
      const pct = Math.round(((agora - antes) / antes) * 100);
      if (Math.abs(pct) < 12) continue;
      if (virada === null || Math.abs(pct) > Math.abs(virada.pct)) {
        virada = { tema: comTempo[i].tema, de: antes, para: agora, pct };
      }
    }

    const itens: string[] = [];
    if (maisLongo && total > 0) {
      const pct = Math.round((maisLongo.segundos / total) * 100);
      itens.push(`<dt>O assunto que ocupou mais tempo</dt>
        <dd>${escapeHtml(maisLongo.tema)} — ${escapeHtml(formatDurationLong(maisLongo.segundos))},
        ${pct}% da conversa.</dd>`);
    }
    if (virada) {
      itens.push(`<dt>Onde o seu ritmo de fala mais mudou</dt>
        <dd>No trecho “${escapeHtml(virada.tema)}”, a sua fala passou de
        ${num(virada.de, 0)} para ${num(virada.para, 0)} palavras por minuto —
        ${Math.abs(virada.pct)}% mais ${virada.pct > 0 ? "rápida" : "lenta"} do que
        no trecho anterior.</dd>`);
    }

    const coincidem = Boolean(maisLongo && virada && virada.tema === maisLongo.tema);
    const pergunta = coincidem
      ? `O assunto que tomou mais tempo é o mesmo em que a sua fala mudou de
         velocidade. O que faz esse assunto ocupar tanto espaço?`
      : maisLongo
        ? `O que faz o assunto mais longo desta conversa ocupar tanto espaço?`
        : `O que desta conversa você gostaria de retomar primeiro?`;

    if (itens.length) {
      blocos.push(`<section>${cab("O que mais pesou nesta conversa")}
        <p>Duas coisas neste documento não dependem de medir a sua voz nem o seu
          rosto: <b>quanto tempo cada assunto ocupou</b> e <b>em que velocidade
          você falava dentro de cada um</b>. As duas saem da própria conversa, e
          são as que se reconhecem numa leitura — por isso vêm primeiro.</p>
        <dl class="peso">${itens.join("")}</dl>
        <p><b>Por que o ritmo importa.</b> Ritmo de fala é quantas palavras você
          diz por minuto. Não existe ritmo certo, e o número sozinho não diz
          nada: pessoas diferentes falam em velocidades diferentes, e a mesma
          pessoa fala diferente em dias diferentes. O que interessa é a
          <b>mudança dentro da mesma conversa</b> — acelerar ou desacelerar ao
          entrar num assunto é uma das formas mais diretas de mostrar que aquele
          assunto tem peso, muitas vezes antes de a pessoa notar que tem.</p>
        <p>Nada disso é interpretação. É o registro de que algo mudou naquele
          ponto. O que a mudança significou só você pode dizer — e é exatamente
          por isso que este documento chega antes da próxima sessão, e não
          depois.</p>
        <p class="pergunta"><b>Para levar à próxima sessão:</b> ${pergunta}</p>
      </section>`);
    }
  }

  // ---- baseline: a referência do dia ----
  if (tem("baseline")) {
    // `escapeHtml` saiu do join: a ausência agora é um <span>, e escapá-la
    // imprimiria a marcação como texto na cara do paciente.
    const linhas = [
      `energia da fala ${medida(base.ipmAvg, 1, vozApurada)}`,
      houveMedida(base.wordsPerMinute)
        ? `ritmo ${num(base.wordsPerMinute, 1)} palavras por minuto`
        : "",
      base.dominantZone === undefined || base.dominantZone === null
        ? ""
        : `zona ${escapeHtml(base.dominantZone)}`,
    ].filter(Boolean);
    blocos.push(`<section>${cab("A sua referência deste dia")}
      <p>Nos primeiros 60 segundos da sessão o sistema mediu como a sua fala e o seu
        rosto estavam naquele momento. É esta a régua usada no resto do documento.</p>
      ${linhas.length ? `<div class="fase"><div class="corpo"><p>${linhas.join(" · ")}.</p></div></div>` : "<p>Não houve calibração registrada nesta sessão.</p>"}
    </section>`);
  }

  // ---- sessionAverage: como a sessão ficou, no conjunto ----
  if (tem("sessionAverage")) {
    // A linha entra SEMPRE, mesmo sem medida — some-la esconderia que houve
    // tentativa. O que muda é o que a célula diz: número quando se mediu,
    // "não medido" quando não.
    const linhas: string[][] = [
      ["Energia da fala", medida(media.ipmAvg, 1, vozApurada), medida(base.ipmAvg, 1, vozApurada)],
      [
        "Variação entre fala e rosto",
        medida(media.idmAvg, 2, vozApurada === false || faceApurada === false ? false : vozApurada),
        medida(base.idmAvg, 2, vozApurada === false || faceApurada === false ? false : vozApurada),
      ],
      ["Ritmo da fala", medida(media.wordsPerMinute, 1, true), medida(base.wordsPerMinute, 1, true)],
    ];
    blocos.push(`<section>${cab("A sessão no conjunto")}
      <table>
        <thead><tr><th>Medida</th><th class="n">Na sessão</th><th class="n">Sua referência</th></tr></thead>
        <tbody>${linhas.map((l) => `<tr><td>${escapeHtml(l[0])}</td><td class="n">${l[1]}</td><td class="n">${l[2]}</td></tr>`).join("")}</tbody>
      </table>
      ${semVoz ? `<p style="margin-top:8px">Nesta sessão o sistema <b>não conseguiu
        medir a sua voz</b> — o áudio não chegou à análise acústica. Os campos
        acima aparecem vazios por isso, e não porque o valor tenha sido zero. As
        leituras de tempo e de ritmo desta conversa não dependem dessa medição e
        continuam válidas.</p>` : ""}
      ${media.emotionalTone ? `<p style="margin-top:7px">Tom predominante ao longo da conversa: ${escapeHtml(media.emotionalTone)}.</p>` : ""}
    </section>`);
  }

  // ---- sessionSummary: o resumo ----
  if (tem("sessionSummary")) {
    const resumo = (report.sessionSummary || {}) as unknown as Record<string, unknown>;
    const texto = teseDaSessao(String(resumo.text || resumo.summary || resumo.theme || "").trim());
    const paragrafos = blocosDeTexto(texto);
    blocos.push(`<section>${cab("Resumo da sessão")}</section>`);
    if (paragrafos.length) paragrafos.forEach((par) => blocos.push(par));
    else blocos.push(`<p class="corrido">Não houve resumo registrado para esta sessão.</p>`);
  }

  // ---- conversationSummaries: o percurso, trecho a trecho ----
  if (tem("conversationSummaries")) {
    blocos.push(`<section>${cab("Percurso da sessão")}</section>`);
    if (cortes.length) {
      // O trecho mais longo e o ritmo do trecho anterior, para a pergunta
      // abaixo sair do que foi MEDIDO e não de uma leitura do conteúdo.
      const segundosPorTrecho = cortes.map((c) => cutSeconds(c as unknown as Record<string, unknown>));
      const totalSegundos = segundosPorTrecho.reduce((a, b) => a + b, 0);
      const indiceMaisLongo = segundosPorTrecho.indexOf(Math.max(...segundosPorTrecho));

      cortes.forEach((c, i) => {
        const r = c as unknown as Record<string, unknown>;
        // A linha de números do modelo aprovado, que faltava aqui: ritmo e tom
        // do trecho. É por causa dela que o percurso conta como seção COM
        // medida — e é o "todas as informações do item" que foi pedido.
        const numeros = [
          houveMedida(r.wordsPerMinute) ? `Ritmo da fala ${num(r.wordsPerMinute, 1)} palavras/min` : "",
          r.emotionalTone ? `tom ${escapeHtml(r.emotionalTone)}` : "",
          r.dominantZone === null || r.dominantZone === undefined ? "" : `zona ${escapeHtml(r.dominantZone)}`,
        ].filter(Boolean).join(" · ");
        blocos.push(`<div class="fase"><div class="badge">Trecho<b>${i + 1}</b></div>
          <div class="corpo"><b>${escapeHtml(cutRange(c))} · ${escapeHtml(c.theme || "Sem tema definido")}</b>
          <p>${escapeHtml(summaryOrFallback(c.summary))}</p>
          ${numeros ? `<div class="numeros">${numeros}</div>` : ""}
          ${perguntaDoTrecho({
            ritmo: houveMedida(r.wordsPerMinute) ? Number(r.wordsPerMinute) : null,
            ritmoAnterior: i > 0 && houveMedida((cortes[i - 1] as unknown as Record<string, unknown>).wordsPerMinute)
              ? Number((cortes[i - 1] as unknown as Record<string, unknown>).wordsPerMinute)
              : null,
            ehMaisLongo: i === indiceMaisLongo && totalSegundos > 0,
            fatia: totalSegundos > 0 ? Math.round((segundosPorTrecho[i] / totalSegundos) * 100) : 0,
          })}</div></div>`);
      });
    } else {
      blocos.push(`<p>Nenhum trecho registrado nesta sessão.</p>`);
    }
  }

  // ---- tenMinuteCuts: as medidas trecho a trecho ----
  //
  // O título dizia "a cada dez minutos" sobre cortes que o profissional fecha à
  // mão: nesta sessão os três tinham 3min37, 12 SEGUNDOS e 7min47. Um título
  // que descreve outra coisa é pior do que nenhum, porque o leitor confia nele.
  //
  // As colunas sem apuração também saem. Uma tabela de quatro colunas com duas
  // vazias não informa que faltou medir — informa que o produto é vazio.
  if (tem("tenMinuteCuts")) {
    const janelas = (report.tenMinuteCuts || []) as unknown as Record<string, unknown>[];
    const temTom = janelas.some((j) => Boolean(j.emotionalTone));
    const colunas = [
      `<th>Trecho</th>`,
      semVoz ? "" : `<th class="n">Energia da fala</th>`,
      `<th class="n">Ritmo</th>`,
      temTom ? `<th>Tom</th>` : "",
    ].filter(Boolean).join("");
    blocos.push(`<section>${cab("Medidas trecho a trecho")}
      ${janelas.length ? `<table>
        <thead><tr>${colunas}</tr></thead>
        <tbody>${janelas.map((j) => `<tr>
          <td>${escapeHtml(j.label || "—")}</td>
          ${semVoz ? "" : `<td class="n">${medida(j.ipmAvg, 1, vozApurada)}</td>`}
          <td class="n">${medida(j.wordsPerMinute, 1, true)}</td>
          ${temTom ? `<td>${escapeHtml(j.emotionalTone || "—")}</td>` : ""}</tr>`).join("")}</tbody>
      </table>` : "<p>Não há trechos registrados nesta sessão.</p>"}
    </section>`);
  }

  // ---- dissonances: os sinais, já traduzidos ----
  if (tem("dissonances")) {
    blocos.push(`<section>${cab("Sinais registrados")}</section>`);
    if (sinais.length) {
      sinais.forEach((item) => {
        blocos.push(`<div class="sinal"><span class="quando">${escapeHtml(formatClock(item.registro.elapsedSeconds))}</span>
          <h3>${escapeHtml(item.visao!.title)}</h3>
          <p>${escapeHtml(item.visao!.description)}</p></div>`);
      });
      blocos.push(`<div class="glossario"><b>Os códigos que aparecem acima</b>
        <div><b>AU6</b> — elevação da bochecha: o movimento que enruga o canto dos olhos.</div>
        <div><b>AU12</b> — elevação do canto da boca: o movimento que levanta os cantos dos lábios.</div>
        <div style="margin-top:8px;color:#6C757D">São nomes técnicos de movimentos
          musculares do rosto, usados internacionalmente. Nomear o movimento não
          interpreta a intenção.</div></div>`);
    } else {
      blocos.push(`<p>Nenhum sinal registrado nesta sessão.</p>`);
    }
  }

  // A tabela de medidas detalhadas SAIU do documento do paciente em 04/09/2026.
  //
  // Vinte e uma linhas — MFCC7, DDMFCC9, ZCR, jitter, shimmer — que não dizem
  // nada a quem não é do ofício. E numa sessão sem apuração acústica todas
  // saíam `0,00`, o que não é neutro: destrói a credibilidade das duas ou três
  // leituras do documento que estavam corretas.
  //
  // Ela continua inteira no relatório do PROFISSIONAL, que é onde tem leitor.
  // O documento do paciente é a pauta da próxima conversa, e pauta com vinte e
  // uma linhas irrelevantes é pauta que não se lê.

  // ---- clinicalNotes: observações registradas durante a sessão ----
  if (tem("clinicalNotes")) {
    const notas = (report.clinicalNotes || []) as unknown as Record<string, unknown>[];
    blocos.push(`<section>${cab("Observações registradas durante a sessão")}</section>`);
    if (notas.length) {
      notas.forEach((nota) => {
        blocos.push(`<div class="fase"><div class="corpo"><p>${escapeHtml(nota.text)}</p></div></div>`);
      });
    } else {
      blocos.push(`<p>Não houve observações registradas durante esta sessão.</p>`);
    }
  }

  // ---- professionalNotes: a palavra do profissional ----
  // Voltou para o catálogo. Ser a mensagem dele justifica a seção existir, não
  // ser obrigatória — e sem texto redigido ela imprimia uma caixa dizendo que
  // não havia nada, o que é pior do que não imprimir. Mandar só as medidas, sem
  // recado, é decisão clínica e agora é dele.
  if (tem("professionalNotes")) {
    const paragrafos = blocosDeTexto(descriptiveText);
    blocos.push(`<section>${cab("Anotações do seu profissional")}</section>`);
    if (paragrafos.length) {
      // A caixa de altura fixa saiu. Ela existia no modelo para mostrar onde o
      // texto entraria; com texto real ela só criava uma moldura que não
      // atravessa folha, e era ela que empurrava a seção inteira para a folha
      // seguinte deixando a anterior pela metade.
      paragrafos.forEach((par) => blocos.push(par));
    } else {
      // A quebra de linha do código saía IMPRESSA: "Seu" numa linha, o resto
      // recuado na seguinte. Dentro de template literal, o recuo é conteúdo.
      blocos.push(`<p class="corrido" style="color:#9CA3AF;font-style:italic">Seu profissional não registrou anotações para esta sessão.</p>`);
    }
  }

  // ---- os limites: SEMPRE, e é a única seção travada ----
  // Não é diagnóstico, não é avaliação sobre quem a pessoa é, não substitui o
  // profissional. O produto inteiro se define por essa fronteira. O risco que
  // esta seção cobre não é o profissional decidir retirá-la — é retirá-la por
  // descuido, e o sistema deixar.
  blocos.push(`<section>${cab("O que este documento não é")}
    <div class="limite">
      <p style="margin:0 0 7px"><b>Não é um diagnóstico.</b> O FROID mede sinais de
        fala e de expressão facial. Medir um sinal não é identificar uma condição.</p>
      <p style="margin:0 0 7px"><b>Não é uma avaliação sobre quem você é.</b> Os
        registros descrevem uma conversa específica, em um dia específico,
        comparada com a sua própria referência daquele dia.</p>
      <p style="margin:0"><b>Não substitui o seu profissional.</b> Quem interpreta,
        contextualiza e conduz é ele. Leve as suas dúvidas para a próxima sessão.</p>
    </div>
  </section>`);

  const rodape = `${tituloDocumento(id)} · Documento pessoal e confidencial`;
  const rodapeFim = `${rodape}${id.contactEmail ? ` · ${id.contactEmail}` : ""}`;
  return head(`Relatório da sessão — ${report.sessionId}`, EXTRA_PACIENTE)
    + documento(blocos, rodape, rodapeFim, id.professionalName)
    + `</body></html>`;
}

export function buildReport(
  audience: ReportAudience,
  report: SessionReportRecord,
  identity?: Partial<ReportIdentity>,
  descriptiveText = "",
  seed?: number,
  /** Blocos escolhidos para o documento do PACIENTE. Ignorado no do profissional,
   *  que sai sempre completo. */
  itensDoPaciente?: string[],
): string {
  return audience === "patient"
    // O texto redigido entra nos DOIS documentos: no do profissional como a
    // seção 06, no do paciente como a seção 04 do modelo aprovado. É a mesma
    // palavra dele, e é ela que liga um documento ao outro.
    ? buildPatientReport(
      report, identity, seed,
      descriptiveText || String(report.patientNotes || ""),
      itensDoPaciente,
    )
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
  // QUEM IMPRIME É O PAGINADOR, quando termina. Aqui havia um print() em 350 ms,
  // de quando o documento saía pronto do gerador. Com a paginação medida — que
  // espera a imagem e remonta o documento — o diálogo passou a abrir com a
  // remontagem em curso, e imprimir enquanto o DOM muda sob o motor de layout
  // travava a aba num documento longo.
  //
  // O temporizador longo abaixo é só rede: se o script não rodar, por erro ou
  // por política de conteúdo, o documento ainda vai para a impressora em vez de
  // ficar aberto sem fazer nada.
  window.setTimeout(() => {
    const w = janela as unknown as Record<string, unknown>;
    if (!w.__froidPaginado) janela.print();
  }, 5000);
  return true;
}
