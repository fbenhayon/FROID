import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  alterarAgendamentoV2,
  cancelarAgendamentoV2,
  criarAgendamentoV2,
  definirDisponibilidadeV2,
  listarAgendaV2,
  listarClinicosV2,
  listarPacientesV2,
  obterCapacidadesPsiqueV2,
  type AgendamentoV2,
  type CapacidadesPsiqueV2,
  type ClinicoV2,
  type EstadoV2,
  type PacienteV2,
} from "../../lib/psique-v2-api";
import {
  DIAS_DA_SEMANA,
  FUSO_PADRAO,
  diaIso,
  gradeDaSemana,
  horaNoFuso,
  instanteDe,
  minutosParaHora,
  motivoDaAgendaIndisponivel,
  papelNaAgenda,
  semanaDe,
} from "../../lib/agenda-interna";
import { usuarioArmazenado } from "../../lib/contexto-organizacao";

/**
 * A agenda interna da clínica (Psique V2, fase 5 do painel — 19/10/2026).
 *
 * O servidor é a fonte: o atendimento interno é a autoridade, a dupla marcação
 * é impossível no banco, e os papéis são checados lá. Esta tela monta a
 * semana, pede e mostra. Dois modos: "clinica" (quem opera a agenda de todos:
 * secretária, administrador e supervisor) e "propria" (o clínico, só a sua).
 *
 * Decisões do dono (18/10/2026): a agenda interna vira a fonte e o Google só
 * espelha; o supervisor vê a agenda geral e marca para os profissionais; o
 * nome do paciente aparece para secretária, administrador e o próprio
 * profissional — o supervisor recebe identificadores.
 */
export function AgendaInterna({ modo }: { modo: "clinica" | "propria" }) {
  const [capacidades, setCapacidades] = useState<EstadoV2<CapacidadesPsiqueV2>>({
    estado: "indisponivel",
    motivo: "CARREGANDO",
  });
  const [clinicos, setClinicos] = useState<ClinicoV2[]>([]);
  const [pacientes, setPacientes] = useState<PacienteV2[]>([]);
  const [comNomes, setComNomes] = useState(true);
  const [agendamentos, setAgendamentos] = useState<AgendamentoV2[]>([]);
  const [referencia, setReferencia] = useState(() => new Date());
  const [aviso, setAviso] = useState("");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [editando, setEditando] = useState<AgendamentoV2 | null>(null);
  const [form, setForm] = useState({ clinico: "", paciente: "", dia: diaIso(new Date()), hora: "09:00", duracao: "50" });
  const [disponibilidade, setDisponibilidade] = useState({ clinico: "", weekday: "1", inicio: "08:00", fim: "18:00" });

  const dias = useMemo(() => semanaDe(referencia), [referencia]);
  const papel = useMemo(() => papelNaAgenda(capacidades), [capacidades]);
  const emailProprio = String((usuarioArmazenado() as { email?: string } | null)?.email || "").toLowerCase();
  const clinicoProprio = useMemo(
    () => clinicos.find((c) => c.email.toLowerCase() === emailProprio) || null,
    [clinicos, emailProprio],
  );
  const clinicosVisiveis = useMemo(
    () => (modo === "propria" ? (clinicoProprio ? [clinicoProprio] : []) : clinicos),
    [modo, clinicos, clinicoProprio],
  );
  const podeOperarTodos = Boolean(papel?.geral) && modo === "clinica";
  const grade = useMemo(() => gradeDaSemana(agendamentos, dias, FUSO_PADRAO), [agendamentos, dias]);
  const rotuloDoPaciente = useCallback(
    (item: AgendamentoV2) =>
      item.patient_name ||
      pacientes.find((p) => p.patient_id === item.patient_id)?.label ||
      `Paciente ${item.patient_id.slice(-4)}`,
    [pacientes],
  );

  const carregarAgenda = useCallback(async () => {
    const inicio = dias[0];
    const fim = new Date(dias[6].getFullYear(), dias[6].getMonth(), dias[6].getDate() + 1);
    const resposta = await listarAgendaV2(inicio.toISOString(), fim.toISOString());
    if (resposta.estado === "ok") {
      setAgendamentos(resposta.dados.appointments);
      setErro("");
    } else {
      setAgendamentos([]);
      setErro(`A agenda não pôde ser lida: ${resposta.motivo}.`);
    }
  }, [dias]);

  useEffect(() => {
    let ativo = true;
    void obterCapacidadesPsiqueV2().then((r) => ativo && setCapacidades(r));
    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    if (!papel) return;
    let ativo = true;
    void listarClinicosV2().then((r) => {
      if (!ativo) return;
      if (r.estado === "ok") setClinicos(r.dados.clinicians);
    });
    void listarPacientesV2().then((r) => {
      if (!ativo) return;
      if (r.estado === "ok") {
        setPacientes(r.dados.patients);
        setComNomes(r.dados.with_names);
      }
    });
    return () => {
      ativo = false;
    };
  }, [papel]);

  useEffect(() => {
    if (!papel) return;
    void carregarAgenda();
  }, [papel, carregarAgenda]);

  useEffect(() => {
    // Clínico: o formulário aponta para ele mesmo; os outros escolhem.
    if (modo === "propria" && clinicoProprio) {
      setForm((f) => ({ ...f, clinico: clinicoProprio.membership_id }));
      setDisponibilidade((d) => ({ ...d, clinico: clinicoProprio.membership_id }));
    } else if (!form.clinico && clinicos[0]) {
      setForm((f) => ({ ...f, clinico: clinicos[0].membership_id }));
      setDisponibilidade((d) => ({ ...d, clinico: clinicos[0].membership_id }));
    }
  }, [modo, clinicoProprio, clinicos, form.clinico]);

  const motivo = motivoDaAgendaIndisponivel(capacidades);
  if (motivo) {
    return (
      <section data-secao="agenda-interna" className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="text-sm font-black text-slate-100">Agenda</h2>
        <p className="mt-2 text-xs text-slate-400">{motivo}</p>
      </section>
    );
  }
  if (modo === "propria" && !papel?.clinico) {
    return (
      <section data-secao="agenda-interna" className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="text-sm font-black text-slate-100">Minha agenda</h2>
        <p className="mt-2 text-xs text-slate-400">
          Seu papel nesta clínica não é de clínico. A agenda geral está em Agenda da clínica.
        </p>
      </section>
    );
  }

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setAviso("");
    setErro("");
    const inicio = instanteDe(form.dia, form.hora, FUSO_PADRAO);
    const duracao = Number(form.duracao);
    if (!inicio || !Number.isFinite(duracao) || duracao <= 0) {
      setErro("Informe dia, hora e duração em minutos.");
      return;
    }
    const fim = new Date(new Date(inicio).getTime() + duracao * 60000).toISOString();
    setSalvando(true);
    try {
      if (editando) {
        const r = await alterarAgendamentoV2(editando.appointment_id, {
          expected_version: editando.version,
          start_at: inicio,
          end_at: fim,
        });
        if (r.estado === "ok" && r.dados.applied) setAviso("Atendimento reagendado.");
        else setErro(`Não reagendado: ${r.estado === "ok" ? r.dados.code || "recusado" : r.motivo}.`);
        setEditando(null);
      } else {
        if (!form.paciente || !form.clinico) {
          setErro("Escolha o clínico e o paciente.");
          return;
        }
        const r = await criarAgendamentoV2(
          { patient_id: form.paciente, clinician_membership_id: form.clinico, start_at: inicio, end_at: fim, timezone: FUSO_PADRAO },
          crypto.randomUUID(),
        );
        if (r.estado === "ok") setAviso(r.dados.created ? "Atendimento marcado." : "Este atendimento já estava marcado.");
        else setErro(`Não marcado: ${traduzirMotivo(r.motivo)}.`);
      }
      await carregarAgenda();
    } finally {
      setSalvando(false);
    }
  };

  const cancelar = async (item: AgendamentoV2) => {
    if (!window.confirm(`Cancelar o atendimento de ${horaNoFuso(item.start_at, FUSO_PADRAO)}?`)) return;
    const r = await cancelarAgendamentoV2(item.appointment_id, { expected_version: item.version, reason: "painel" });
    if (r.estado === "ok" && r.dados.applied) setAviso("Atendimento cancelado.");
    else setErro(`Não cancelado: ${r.estado === "ok" ? r.dados.code || "recusado" : r.motivo}.`);
    await carregarAgenda();
  };

  const prepararReagendamento = (item: AgendamentoV2) => {
    setEditando(item);
    setForm((f) => ({
      ...f,
      clinico: item.clinician_membership_id,
      paciente: item.patient_id,
      dia: diaIso(new Date(item.start_at)),
      hora: horaNoFuso(item.start_at, FUSO_PADRAO),
      duracao: String(Math.round((new Date(item.end_at).getTime() - new Date(item.start_at).getTime()) / 60000)),
    }));
    setAviso("Ajuste dia, hora ou duração e confirme o reagendamento.");
  };

  const salvarDisponibilidade = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setAviso("");
    setErro("");
    const inicio = minutosDe(disponibilidade.inicio);
    const fim = minutosDe(disponibilidade.fim);
    if (inicio === null || fim === null || fim <= inicio || !disponibilidade.clinico) {
      setErro("Informe o clínico e uma janela com fim depois do início.");
      return;
    }
    const r = await definirDisponibilidadeV2({
      clinician_membership_id: disponibilidade.clinico,
      weekday: Number(disponibilidade.weekday),
      start_minute: inicio,
      end_minute: fim,
      timezone: FUSO_PADRAO,
    });
    if (r.estado === "ok") {
      setAviso("Disponibilidade salva.");
      const lista = await listarClinicosV2();
      if (lista.estado === "ok") setClinicos(lista.dados.clinicians);
    } else {
      setErro(`Disponibilidade não salva: ${traduzirMotivo(r.motivo)}.`);
    }
  };

  const mover = (semanas: number) =>
    setReferencia((r) => new Date(r.getFullYear(), r.getMonth(), r.getDate() + 7 * semanas));

  return (
    <section data-secao="agenda-interna" className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-black text-slate-100">
          {modo === "clinica" ? "Agenda da clínica" : "Minha agenda"}
        </h2>
        <div className="flex items-center gap-2 text-xs">
          <button type="button" onClick={() => mover(-1)} className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800">
            ◀ semana
          </button>
          <span className="font-mono text-slate-300">
            {diaIso(dias[0])} a {diaIso(dias[6])}
          </span>
          <button type="button" onClick={() => mover(1)} className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800">
            semana ▶
          </button>
          <button type="button" onClick={() => setReferencia(new Date())} className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800">
            hoje
          </button>
        </div>
      </div>
      <p className="mt-1 text-[11px] text-slate-500">
        Horários em {FUSO_PADRAO}. A agenda interna é a fonte; o Google Calendar passa a espelhá-la.
        {!comNomes ? " Você vê identificadores, não nomes de pacientes." : ""}
      </p>

      {aviso ? <p data-campo="aviso" className="mt-2 text-xs text-cyan-200">{aviso}</p> : null}
      {erro ? <p data-campo="erro" className="mt-2 text-xs text-red-300">{erro}</p> : null}

      <div className="mt-3 overflow-x-auto">
        <table className="min-w-max table-fixed text-left text-[11px]">
          <thead className="text-[9px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-40 px-2 py-1">Clínico</th>
              {dias.map((dia) => (
                <th key={diaIso(dia)} className="w-36 px-2 py-1">
                  {DIAS_DA_SEMANA[dia.getDay()]} {String(dia.getDate()).padStart(2, "0")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {clinicosVisiveis.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-2 py-3 text-slate-500">
                  Nenhum clínico com papel V2 nesta clínica ainda.
                </td>
              </tr>
            ) : null}
            {clinicosVisiveis.map((clinico) => (
              <tr key={clinico.membership_id} className="align-top">
                <td className="px-2 py-2">
                  <p className="font-bold text-slate-100">{clinico.email}</p>
                  <p className="text-[10px] text-slate-500">
                    {clinico.availability.filter((a) => a.active).length
                      ? clinico.availability
                          .filter((a) => a.active)
                          .map((a) => `${DIAS_DA_SEMANA[a.weekday]} ${minutosParaHora(a.start_minute)}-${minutosParaHora(a.end_minute)}`)
                          .join(" · ")
                      : "sem disponibilidade cadastrada"}
                  </p>
                </td>
                {dias.map((dia) => {
                  const itens = grade.get(clinico.membership_id)?.get(diaIso(dia)) || [];
                  return (
                    <td key={diaIso(dia)} className="px-2 py-2">
                      {itens.map((item) => (
                        <div
                          key={item.appointment_id}
                          data-agendamento={item.appointment_id}
                          className={`mb-1 rounded border px-1.5 py-1 ${
                            item.appointment_status === "CANCELLED"
                              ? "border-slate-800 text-slate-500 line-through"
                              : "border-cyan-800 bg-cyan-950/40 text-slate-100"
                          }`}
                        >
                          <p className="font-mono">
                            {horaNoFuso(item.start_at, FUSO_PADRAO)}–{horaNoFuso(item.end_at, FUSO_PADRAO)}
                          </p>
                          <p className="truncate">{rotuloDoPaciente(item)}</p>
                          <p className="text-[9px] uppercase text-slate-400">{item.appointment_status}</p>
                          {item.appointment_status !== "CANCELLED" &&
                          (podeOperarTodos || item.clinician_membership_id === clinicoProprio?.membership_id) ? (
                            <div className="mt-1 flex gap-1">
                              <button type="button" onClick={() => prepararReagendamento(item)} className="rounded border border-slate-700 px-1 text-[9px] hover:bg-slate-800">
                                reagendar
                              </button>
                              <button type="button" onClick={() => void cancelar(item)} className="rounded border border-red-900 px-1 text-[9px] text-red-300 hover:bg-red-950">
                                cancelar
                              </button>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form onSubmit={(e) => void enviar(e)} className="mt-4 grid gap-2 rounded border border-slate-800 bg-slate-950 p-3 text-xs md:grid-cols-6">
        <p className="md:col-span-6 text-[10px] font-bold uppercase tracking-wide text-slate-400">
          {editando ? "Reagendar atendimento" : "Marcar atendimento"}
        </p>
        <label className="flex flex-col gap-1">
          Clínico
          <select
            value={form.clinico}
            disabled={modo === "propria" || Boolean(editando)}
            onChange={(e) => setForm((f) => ({ ...f, clinico: e.target.value }))}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
          >
            {clinicosVisiveis.map((c) => (
              <option key={c.membership_id} value={c.membership_id}>{c.email}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 md:col-span-2">
          Paciente
          <select
            value={form.paciente}
            disabled={Boolean(editando)}
            onChange={(e) => setForm((f) => ({ ...f, paciente: e.target.value }))}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
          >
            <option value="">escolha</option>
            {pacientes.map((p) => (
              <option key={p.patient_id} value={p.patient_id}>{p.label}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Dia
          <input type="date" value={form.dia} onChange={(e) => setForm((f) => ({ ...f, dia: e.target.value }))} className="rounded border border-slate-700 bg-slate-900 px-2 py-1" />
        </label>
        <label className="flex flex-col gap-1">
          Hora
          <input type="time" value={form.hora} onChange={(e) => setForm((f) => ({ ...f, hora: e.target.value }))} className="rounded border border-slate-700 bg-slate-900 px-2 py-1" />
        </label>
        <label className="flex flex-col gap-1">
          Minutos
          <input type="number" min={5} value={form.duracao} onChange={(e) => setForm((f) => ({ ...f, duracao: e.target.value }))} className="rounded border border-slate-700 bg-slate-900 px-2 py-1" />
        </label>
        <div className="flex items-end gap-2 md:col-span-6">
          <button type="submit" disabled={salvando} className="rounded bg-cyan-700 px-3 py-1 font-bold text-white hover:bg-cyan-800 disabled:opacity-60">
            {editando ? "Confirmar reagendamento" : "Marcar"}
          </button>
          {editando ? (
            <button type="button" onClick={() => setEditando(null)} className="rounded border border-slate-700 px-3 py-1 hover:bg-slate-800">
              desistir
            </button>
          ) : null}
        </div>
      </form>

      {(podeOperarTodos || papel?.clinico) ? (
        <form onSubmit={(e) => void salvarDisponibilidade(e)} className="mt-3 grid gap-2 rounded border border-slate-800 bg-slate-950 p-3 text-xs md:grid-cols-5">
          <p className="md:col-span-5 text-[10px] font-bold uppercase tracking-wide text-slate-400">
            Disponibilidade semanal {modo === "propria" ? "(a sua)" : ""}
          </p>
          <label className="flex flex-col gap-1">
            Clínico
            <select
              value={disponibilidade.clinico}
              disabled={modo === "propria"}
              onChange={(e) => setDisponibilidade((d) => ({ ...d, clinico: e.target.value }))}
              className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
            >
              {clinicosVisiveis.map((c) => (
                <option key={c.membership_id} value={c.membership_id}>{c.email}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            Dia da semana
            <select value={disponibilidade.weekday} onChange={(e) => setDisponibilidade((d) => ({ ...d, weekday: e.target.value }))} className="rounded border border-slate-700 bg-slate-900 px-2 py-1">
              {DIAS_DA_SEMANA.map((nome, i) => (
                <option key={nome} value={String(i)}>{nome}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            Início
            <input type="time" value={disponibilidade.inicio} onChange={(e) => setDisponibilidade((d) => ({ ...d, inicio: e.target.value }))} className="rounded border border-slate-700 bg-slate-900 px-2 py-1" />
          </label>
          <label className="flex flex-col gap-1">
            Fim
            <input type="time" value={disponibilidade.fim} onChange={(e) => setDisponibilidade((d) => ({ ...d, fim: e.target.value }))} className="rounded border border-slate-700 bg-slate-900 px-2 py-1" />
          </label>
          <div className="flex items-end">
            <button type="submit" className="rounded border border-cyan-800 px-3 py-1 font-bold text-cyan-100 hover:bg-cyan-950">
              Salvar janela
            </button>
          </div>
        </form>
      ) : null}
    </section>
  );
}

function minutosDe(hora: string): number | null {
  const partes = /^(\d{1,2}):(\d{2})$/.exec(hora);
  if (!partes) return null;
  return Number(partes[1]) * 60 + Number(partes[2]);
}

/** Os códigos do servidor que a tela sabe explicar; o resto sai como veio. */
function traduzirMotivo(codigo: string): string {
  const frases: Record<string, string> = {
    APPOINTMENT_CONFLICT: "o clínico já tem atendimento nesse horário",
    OUTSIDE_AVAILABILITY: "fora da disponibilidade cadastrada do clínico",
    OWN_AGENDA_ONLY: "você só pode operar a sua própria agenda",
    OWN_AVAILABILITY_ONLY: "você só pode definir a sua própria disponibilidade",
    APPOINTMENT_PATIENT_REQUIRED: "o paciente não está ativo nesta clínica",
    APPOINTMENT_CLINICIAN_REQUIRED: "a pessoa escolhida não tem papel de clínico",
    RBAC_V2_NOT_ENABLED: "a clínica ainda não ativou os papéis V2",
    PSIQUE_SCHEDULING_ROLE_DENIED: "seu papel não inclui agenda",
  };
  return frases[codigo] || codigo;
}
