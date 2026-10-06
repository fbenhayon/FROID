import type { FacialAnalysis, FacialEvent } from "../lib/facial-analysis";

export function FacialAnalysisPanel({ analysis, events, historical = false }: {
  analysis?: FacialAnalysis; events: FacialEvent[]; historical?: boolean;
}) {
  const stale = !historical && analysis?.expires_at_ms !== undefined && Date.now() > analysis.expires_at_ms;
  const available = analysis?.status === "measured" && !stale;
  return <section className="space-y-3 text-[11px]">
    <h3 className="font-bold uppercase text-cyan-200">Interpretação facial · sete famílias</h3>
    <p className="text-slate-400">Padrões observados, não diagnóstico ou prova de dissonância.</p>
    {historical && <p className="text-slate-400">Leitura arquivada da sessão; não representa uma medida atual.</p>}
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
    {available && analysis?.action_units && <details>
      <summary>Medidas subjacentes (proxies de AU)</summary>
      <div className="grid grid-cols-2 gap-1 py-2">
        {Object.entries(analysis.action_units).map(([au, value]) =>
          <p key={au}>{au}: {value === null ? "não apurada" : value.toFixed(4)}</p>)}
      </div>
      <p>AU17: proxy inferior; AU23: sem mapeamento. Coeficientes brutos e estimativas legadas são preservados no motor.</p>
    </details>}
    {analysis && <details><summary>Limites da interpretação</summary>
      {analysis.limitations.map(limit => <p key={limit} className="mt-1 text-slate-400">{limit}</p>)}
    </details>}
    <p className="text-amber-200">{analysis?.dissonance.reason || "Dissonância facial-vocal: sem capacidade de apuração."}</p>
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
