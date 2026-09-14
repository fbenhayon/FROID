import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../../lib/api";

/**
 * A agenda do profissional, na coluna lateral do dashboard resumido.
 *
 * Lê o Google Agenda conectado pelo Administrativo. São TRÊS estados
 * diferentes, e confundi-los manda a pessoa para o lugar errado:
 *
 *   - o servidor não tem credencial do Google (`configured: false`) — não
 *     adianta oferecer "conectar", o botão levaria a um 503;
 *   - o servidor tem, e esta conta ainda não conectou — aí sim, convite;
 *   - conectado, e a leitura pode falhar — e a falha aparece, em vez de virar
 *     uma coluna vazia que parece "nenhum compromisso".
 */

type ConnectionStatus = {
  configured?: boolean;
  connected?: boolean;
  selected_calendar_summary?: string;
};

type CalendarEvent = {
  id: string;
  summary: string;
  start?: { dateTime?: string; date?: string };
  end?: { dateTime?: string; date?: string };
  htmlLink?: string;
};

type Compromisso = {
  id: string;
  titulo: string;
  inicio: Date | null;
  diaInteiro: boolean;
  link: string;
};

function inicioDoDia(referencia: Date) {
  const dia = new Date(referencia);
  dia.setHours(0, 0, 0, 0);
  return dia;
}

function normalizar(evento: CalendarEvent): Compromisso {
  const bruto = evento.start?.dateTime || evento.start?.date || "";
  const data = bruto ? new Date(bruto) : null;
  return {
    id: String(evento.id || bruto || Math.random()),
    titulo: evento.summary || "(sem título)",
    inicio: data && Number.isFinite(data.getTime()) ? data : null,
    diaInteiro: !evento.start?.dateTime && Boolean(evento.start?.date),
    link: evento.htmlLink || "",
  };
}

function rotuloDoDia(data: Date, hoje: Date) {
  const dias = Math.round(
    (inicioDoDia(data).getTime() - inicioDoDia(hoje).getTime()) / 86400000,
  );
  if (dias === 0) return "Hoje";
  if (dias === 1) return "Amanhã";
  return data.toLocaleDateString(undefined, { weekday: "short", day: "2-digit", month: "2-digit" });
}

function horario(compromisso: Compromisso) {
  if (compromisso.diaInteiro) return "dia inteiro";
  if (!compromisso.inicio) return "--";
  return compromisso.inicio.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

const DIAS_A_FRENTE = 3;

export const AgendaDoProfissional: React.FC<{ tr?: (texto: string) => string }> = ({
  tr = (texto: string) => texto,
}) => {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [compromissos, setCompromissos] = useState<Compromisso[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    const token = localStorage.getItem("froid_token") || "";
    const headers: Record<string, string> = token
      ? { Authorization: `Bearer ${token}` }
      : {};

    const carregar = async () => {
      try {
        const respostaStatus = await fetch(apiUrl("/api/google-calendar/status"), { headers });
        if (!respostaStatus.ok) {
          throw new Error(
            respostaStatus.status === 401
              ? "Sua sessão expirou."
              : `Não foi possível ler o estado da agenda (erro ${respostaStatus.status}).`,
          );
        }
        const dadosStatus: ConnectionStatus = await respostaStatus.json();
        if (!ativo) return;
        setStatus(dadosStatus);
        if (!dadosStatus.configured || !dadosStatus.connected) return;

        const inicio = inicioDoDia(new Date());
        const fim = new Date(inicio);
        fim.setDate(fim.getDate() + DIAS_A_FRENTE);
        const busca = new URLSearchParams({
          time_min: inicio.toISOString(),
          time_max: fim.toISOString(),
          max_results: "25",
        });
        const respostaEventos = await fetch(
          apiUrl(`/api/google-calendar/events?${busca.toString()}`),
          { headers },
        );
        if (!respostaEventos.ok) {
          throw new Error(`O Google Agenda não respondeu (erro ${respostaEventos.status}).`);
        }
        const dados = await respostaEventos.json();
        if (!ativo) return;
        const itens: CalendarEvent[] = Array.isArray(dados?.items) ? dados.items : [];
        setCompromissos(itens.map(normalizar).filter((item) => item.inicio));
        setErro("");
      } catch (falha) {
        if (ativo) {
          setErro(falha instanceof Error ? falha.message : "Agenda indisponível.");
        }
      } finally {
        if (ativo) setCarregando(false);
      }
    };

    void carregar();
    return () => {
      ativo = false;
    };
  }, []);

  const agora = new Date();
  const porDia = new Map<string, Compromisso[]>();
  compromissos.forEach((compromisso) => {
    if (!compromisso.inicio) return;
    const chave = rotuloDoDia(compromisso.inicio, agora);
    porDia.set(chave, [...(porDia.get(chave) || []), compromisso]);
  });

  const moldura = (conteudo: React.ReactNode) => (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="text-sm font-black text-slate-100">{tr("Minha agenda")}</h2>
      <div className="mt-3">{conteudo}</div>
    </section>
  );

  if (carregando) {
    return moldura(
      <p role="status" aria-live="polite" className="text-xs text-slate-400">
        {tr("Estamos executando sua Solicitação, aguarde por favor")}
      </p>,
    );
  }

  if (erro) {
    return moldura(
      <p role="alert" className="text-xs font-semibold text-amber-200">
        {erro}
      </p>,
    );
  }

  // O servidor não tem credencial do Google. Oferecer "conectar" aqui daria um
  // botão que só sabe falhar; quem resolve isto é quem opera o servidor.
  if (status && status.configured === false) {
    return moldura(
      <p className="text-xs text-slate-400">
        {tr("A integração com o Google Agenda não está configurada neste servidor.")}
      </p>,
    );
  }

  if (!status?.connected) {
    return moldura(
      <div className="space-y-3">
        <p className="text-xs text-slate-400">
          {tr("Conecte o Google Agenda para ver seus compromissos aqui.")}
        </p>
        <button
          type="button"
          onClick={() => navigate("/settings")}
          className="w-full rounded-lg border border-cyan-800 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100 hover:bg-cyan-900"
        >
          {tr("Conectar Google Agenda")}
        </button>
      </div>,
    );
  }

  if (!compromissos.length) {
    return moldura(
      <p className="text-xs text-slate-400">
        {tr("Nenhum compromisso nos próximos dias.")}
      </p>,
    );
  }

  return moldura(
    <div className="space-y-4">
      {Array.from(porDia.entries()).map(([dia, itens]) => (
        <div key={dia}>
          <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">
            {tr(dia)}
          </p>
          <ul className="mt-2 space-y-2">
            {itens.map((compromisso) => {
              const passou = Boolean(
                compromisso.inicio && compromisso.inicio.getTime() < agora.getTime(),
              );
              const conteudo = (
                <>
                  <span className="shrink-0 font-mono text-[11px] text-slate-300">
                    {horario(compromisso)}
                  </span>
                  <span className="min-w-0 flex-1 truncate" title={compromisso.titulo}>
                    {compromisso.titulo}
                  </span>
                </>
              );
              const classe = `flex items-baseline gap-2 rounded px-2 py-1.5 text-xs ${
                passou ? "text-slate-500" : "text-slate-100"
              }`;
              return (
                <li key={compromisso.id}>
                  {compromisso.link ? (
                    <a
                      href={compromisso.link}
                      target="_blank"
                      rel="noreferrer"
                      className={`${classe} hover:bg-slate-800`}
                    >
                      {conteudo}
                    </a>
                  ) : (
                    <div className={classe}>{conteudo}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {status.selected_calendar_summary ? (
        <p className="border-t border-slate-800 pt-2 text-[10px] text-slate-500">
          {status.selected_calendar_summary}
        </p>
      ) : null}
    </div>,
  );
};
