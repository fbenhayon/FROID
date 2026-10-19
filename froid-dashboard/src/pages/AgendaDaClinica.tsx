import { useNavigate } from "react-router-dom";
import { AgendaInterna } from "../components/psique/AgendaInterna";

/** A agenda de todos os clínicos da clínica, para quem opera a agenda geral. */
export function AgendaDaClinica() {
  const nav = useNavigate();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Clínica</p>
            <h1 className="text-xl font-bold text-slate-100">Agenda da clínica</h1>
          </div>
          <button
            type="button"
            onClick={() => nav("/dashboard")}
            className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-slate-800"
          >
            Voltar ao painel
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-6">
        <AgendaInterna modo="clinica" />
      </main>
    </div>
  );
}
