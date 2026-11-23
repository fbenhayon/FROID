import {
  groupFacialEventsByCut, mmss, speechAtSecond,
  type FacialAnalysis, type FacialEvent,
} from "../lib/facial-analysis";

// Decisão do dono, 08/11/2026: as medidas subjacentes (proxies de AU) saem da
// tela — continuam gravadas no motor —, e os limites, que são texto fixo e
// idêntico em toda sessão, viram um link em vez de uma lista repetida.
const LIMITS_URL = "https://www.froid.com.br/etica.html";

interface Procedencia { amostras: number; amostrasComFaceReal: number }

function FacialFooter({ analysis }: { analysis?: FacialAnalysis }) {
  return <p className="text-slate-500">
    {analysis?.dissonance.reason || "Dissonância facial-vocal: sem capacidade de apuração."}{" "}
    <a className="underline hover:text-slate-300" href={LIMITS_URL} target="_blank" rel="noreferrer">
      Limites da leitura facial
    </a>
  </p>;
}

function CaptureQuality({ procedencia }: { procedencia?: Procedencia }) {
  const total = procedencia?.amostras;
  const face = procedencia?.amostrasComFaceReal;
  if (typeof total !== "number" || typeof face !== "number" || total <= 0) {
    return <p className="text-slate-400">Qualidade da captura facial: sem capacidade de apuração neste relatório.</p>;
  }
  const pct = Math.round((face / total) * 100);
  return <p className={pct < 50 ? "text-amber-200" : "text-slate-400"}>
    Captura facial: leitura real em {face} de {total} amostras da sessão ({pct}%).
    {pct < 50 && " Menos da metade da sessão teve rosto medido; a ausência de padrões não é informativa."}
  </p>;
}

function BaselineLine({ analysis }: { analysis?: FacialAnalysis }) {
  const b = analysis?.facial_baseline;
  if (!b) {
    return <p className="text-slate-400">Referência facial individual: não registrada neste relatório (anterior à calibração facial).</p>;
  }
  const measuring = " Modo de medição: os padrões ainda não são filtrados por ela.";
  if (b.status === "ready") {
    return <p className="text-slate-400">Referência facial individual: calibrada com {b.calibration_frames} quadros nos {b.window_s} s iniciais.{measuring}</p>;
  }
  if (b.status === "insufficient") {
    return <p className="text-amber-200">Referência facial individual insuficiente: {b.calibration_frames} quadros nos {b.window_s} s iniciais (mínimo {b.min_frames}).{measuring}</p>;
  }
  return <p className="text-slate-400">Referência facial individual: calibração não concluída nesta sessão.</p>;
}

function familyCounts(events: FacialEvent[]): string {
  const counts = new Map<string, number>();
  for (const e of events) counts.set(e.title, (counts.get(e.title) || 0) + 1);
  return [...counts.entries()].map(([title, n]) => `${title} ×${n}`).join(" · ");
}

function EventRow({ event, transcript, transcriptLineSeconds }: {
  event: FacialEvent; transcript?: string; transcriptLineSeconds?: number[];
}) {
  const t = event.recorded_elapsed_seconds;
  const hasTime = typeof t === "number" && Number.isFinite(t);
  const end = event.ended_at_ms ?? event.last_observed_at_ms;
  const duration = Number.isFinite(end) && end >= event.started_at_ms ? (end - event.started_at_ms) / 1000 : null;
  const speech = hasTime ? speechAtSecond(transcript, transcriptLineSeconds, t as number) : null;
  return <div className="rounded border border-slate-700 p-2">
    <p>
      <span className="font-mono text-cyan-100">{hasTime ? mmss(t as number)
        : new Date(event.started_at_ms).toLocaleTimeString("pt-BR")}</span>{" "}
      <span className="font-bold">{event.title}</span>
      <span className="text-slate-400">
        {" "}· {event.observations} quadros{duration !== null ? ` · ${duration.toFixed(1)} s` : ""}
        {event.side && event.side !== "bilateral" ? ` · lado ${event.side === "left" ? "esquerdo" : "direito"}` : ""}
      </span>
    </p>
    {event.ambiguous && <p className="text-amber-200">Coocorrência de famílias; não resolve emoção por ordem de regra.</p>}
    {speech && <p className="mt-1 text-slate-300">Fala no momento: “{speech}”</p>}
  </div>;
}

function HistoricalByCut({ events, cuts, transcript, transcriptLineSeconds, procedencia, analysis }: {
  events: FacialEvent[];
  cuts: Array<{ startSecond: number; endSecond: number }>;
  transcript?: string;
  transcriptLineSeconds?: number[];
  procedencia?: Procedencia;
  analysis?: FacialAnalysis;
}) {
  const grouped = groupFacialEventsByCut(events, cuts);
  const rows = (list: FacialEvent[]) => list.map(e =>
    <EventRow key={e.id} event={e} transcript={transcript} transcriptLineSeconds={transcriptLineSeconds} />);
  return <section className="space-y-3 text-[11px]">
    <h3 className="font-bold uppercase text-cyan-200">Movimentos faciais por corte</h3>
    <p className="text-slate-400">Padrões observados em mais de um quadro, com o instante da sessão e a fala daquele momento. Não são diagnóstico nem prova de emoção.</p>
    <CaptureQuality procedencia={procedencia} />
    <BaselineLine analysis={analysis} />
    {grouped.cuts.map((cut, i) => <div key={`${cut.startSecond}-${cut.endSecond}`} className="space-y-2">
      <p className="font-bold text-slate-200">
        Corte {i + 1} · {mmss(cut.startSecond)}–{mmss(cut.endSecond)}
        <span className="font-normal text-slate-400">
          {cut.events.length ? ` · ${familyCounts(cut.events)}` : " · nenhum padrão facial registrado neste corte"}
        </span>
      </p>
      {rows(cut.events)}
    </div>)}
    {!grouped.cuts.length && !!events.length && <p className="text-slate-400">Cortes não registrados neste relatório; padrões em ordem de ocorrência.</p>}
    {grouped.outsideCuts.length > 0 && <div className="space-y-2">
      <p className="font-bold text-slate-200">{grouped.cuts.length ? "Fora dos cortes registrados" : "Padrões da sessão"}
        <span className="font-normal text-slate-400"> · {familyCounts(grouped.outsideCuts)}</span></p>
      {rows(grouped.outsideCuts)}
    </div>}
    {grouped.withoutTime.length > 0 && <div className="space-y-2">
      <p className="font-bold text-slate-200">Sem instante da sessão registrado
        <span className="font-normal text-slate-400"> · {familyCounts(grouped.withoutTime)}</span></p>
      {rows(grouped.withoutTime)}
    </div>}
    <FacialFooter analysis={analysis} />
  </section>;
}

// Sessão ao vivo, desde 23/11/2026 (pedido do dono: "as sete famílias estão
// sem utilidade para o profissional"). Sete cartões fixos, quase sempre
// dizendo "padrão não detectado", com códigos de AU, não respondiam à
// pergunta de relance: o que apareceu, quando, quantas vezes e no meio de
// qual fala. A tela agora mostra (1) só as famílias presentes NESTA leitura,
// (2) a contagem por família na sessão e (3) os últimos registros com o
// instante, a duração e a fala daquele momento — o mesmo desenho do relatório
// por corte, que o profissional já usa. Nada novo é inferido: são os mesmos
// eventos do motor, apenas em outra ordem.
const ULTIMOS_REGISTROS = 6;

function LiveEventRow({ event, falas }: {
  event: FacialEvent; falas?: Array<{ elapsedSeconds: number; text: string }>;
}) {
  const t = event.recorded_elapsed_seconds;
  const hasTime = typeof t === "number" && Number.isFinite(t);
  const end = event.ended_at_ms ?? event.last_observed_at_ms;
  const duration = Number.isFinite(end) && end >= event.started_at_ms ? (end - event.started_at_ms) / 1000 : null;
  const speech = hasTime && falas?.length
    ? speechAtSecond(
        falas.map(f => f.text.replace(/\n/g, " ")).join("\n"),
        falas.map(f => f.elapsedSeconds),
        t as number,
      )
    : null;
  return <div className="rounded bg-slate-900 px-2 py-1">
    <p>
      <span className="font-mono text-cyan-100">{hasTime ? mmss(t as number)
        : new Date(event.started_at_ms).toLocaleTimeString("pt-BR")}</span>{" "}
      <span className="font-bold">{event.title}</span>
      <span className="text-slate-400">
        {duration !== null ? ` · ${duration.toFixed(1)} s` : ""}
        {event.side && event.side !== "bilateral" ? ` · lado ${event.side === "left" ? "esquerdo" : "direito"}` : ""}
        {event.ambiguous ? " · coocorrência de famílias" : ""}
      </span>
    </p>
    {event.report && <p className="text-slate-400">{event.report}</p>}
    {speech && <p className="text-slate-300">Fala no momento: “{speech}”</p>}
  </div>;
}

export function FacialAnalysisPanel({
  analysis, events, historical = false, cuts, transcript, transcriptLineSeconds, procedencia, falas,
}: {
  analysis?: FacialAnalysis; events: FacialEvent[]; historical?: boolean;
  cuts?: Array<{ startSecond: number; endSecond: number }>;
  transcript?: string; transcriptLineSeconds?: number[];
  procedencia?: Procedencia;
  /** Sessão ao vivo: falas com o segundo da sessão, para "fala no momento". */
  falas?: Array<{ elapsedSeconds: number; text: string }>;
}) {
  if (historical) {
    return <HistoricalByCut events={events} cuts={cuts || []} transcript={transcript}
      transcriptLineSeconds={transcriptLineSeconds} procedencia={procedencia} analysis={analysis} />;
  }
  const stale = analysis?.expires_at_ms !== undefined && Date.now() > analysis.expires_at_ms;
  const available = analysis?.status === "measured" && !stale;
  const presentes = available
    ? (analysis?.families || []).filter(f => f.status === "observed" || f.status === "candidate")
    : [];
  const recentes = [...events].reverse().slice(0, ULTIMOS_REGISTROS);
  return <section className="space-y-2 text-[11px]">
    <h3 className="font-bold uppercase text-cyan-200">Movimentos faciais</h3>
    <div>
      <span className="font-bold text-slate-300">Agora: </span>
      {!available
        ? <span role="status" className="text-amber-200">
            {stale ? "Leitura facial vencida: aguardando um quadro novo." : analysis?.reason || "Sem capacidade de apuração facial nesta janela."}
          </span>
        : presentes.length === 0
          ? <span className="text-slate-400">nenhum padrão facial nesta leitura.</span>
          : <span className="inline-flex flex-wrap gap-1 align-middle">
              {presentes.map(f => <span key={f.id}
                title={f.status === "observed" ? "Padrão repetido em quadros distintos" : "Candidato: aguardando outro quadro"}
                className={f.status === "observed"
                  ? "rounded bg-cyan-800 px-1.5 py-0.5 font-bold text-cyan-50"
                  : "rounded bg-slate-800 px-1.5 py-0.5 text-slate-300"}>
                {f.title}{f.status === "candidate" ? " ?" : ""}
              </span>)}
              {analysis?.ambiguous && <span className="text-amber-200">· mais de uma família compatível; interpretação ambígua</span>}
            </span>}
    </div>
    <p className="text-slate-400">
      <span className="font-bold text-slate-300">Na sessão: </span>
      {events.length ? familyCounts(events) : "nenhum padrão registrado até agora."}
    </p>
    {recentes.length > 0 && <div className="space-y-1">
      <p className="font-bold text-slate-300">Últimos registros</p>
      {recentes.map(e => <LiveEventRow key={e.id} event={e} falas={falas} />)}
    </div>}
    <FacialFooter analysis={analysis} />
  </section>;
}
