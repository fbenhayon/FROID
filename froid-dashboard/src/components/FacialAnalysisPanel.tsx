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

export function FacialAnalysisPanel({
  analysis, events, historical = false, cuts, transcript, transcriptLineSeconds, procedencia,
}: {
  analysis?: FacialAnalysis; events: FacialEvent[]; historical?: boolean;
  cuts?: Array<{ startSecond: number; endSecond: number }>;
  transcript?: string; transcriptLineSeconds?: number[];
  procedencia?: Procedencia;
}) {
  if (historical) {
    return <HistoricalByCut events={events} cuts={cuts || []} transcript={transcript}
      transcriptLineSeconds={transcriptLineSeconds} procedencia={procedencia} analysis={analysis} />;
  }
  const stale = analysis?.expires_at_ms !== undefined && Date.now() > analysis.expires_at_ms;
  const available = analysis?.status === "measured" && !stale;
  return <section className="space-y-3 text-[11px]">
    <h3 className="font-bold uppercase text-cyan-200">Interpretação facial · sete famílias</h3>
    <p className="text-slate-400">Padrões observados, não diagnóstico ou prova de dissonância.</p>
    {!available && <p role="status" className="text-amber-200">
      {stale ? "Leitura facial vencida: aguardando um quadro novo." : analysis?.reason || "Sem capacidade de apuração facial nesta janela."}
    </p>}
    {available && analysis?.ambiguous && <p className="text-amber-200">Mais de uma família compatível; interpretação ambígua.</p>}
    <div className="grid grid-cols-1 gap-2">
      {analysis?.families.map(family => <div key={family.id} className="rounded border border-slate-700 p-2">
        <p className="font-bold">{family.title}</p>
        <p className="text-slate-400">{!available ? "Sem medidas atuais" : family.status === "observed" ? "Padrão repetido em quadros distintos"
          : family.status === "candidate" ? "Candidato — aguardando outro quadro"
          : family.status === "unavailable" ? "Sem medidas suficientes" : "Padrão não detectado nesta leitura"}</p>
        {available && family.variants.map(variant => <p key={variant.id} className="font-mono text-cyan-100">
          {variant.id} · {variant.aus.join(" + ")}{variant.side ? ` · ${variant.side}` : ""}
        </p>)}
      </div>)}
    </div>
    <FacialFooter analysis={analysis} />
    <details><summary>Registro facial · {events.length} padrões</summary>
      <div className="max-h-48 space-y-2 overflow-y-auto">
        {[...events].reverse().map(event => <div key={event.id} className="rounded border border-slate-700 p-2">
          <p className="font-bold">{event.title}</p>
          <p>{new Date(event.started_at_ms).toLocaleTimeString("pt-BR")} · {event.observations} quadros · {event.variant}</p>
          {event.ambiguous && <p>Coocorrência de famílias; não resolve emoção por ordem de regra.</p>}
          <p>{event.report}</p>
        </div>)}
      </div>
    </details>
  </section>;
}
