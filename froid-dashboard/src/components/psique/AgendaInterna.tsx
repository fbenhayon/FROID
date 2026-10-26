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
  diaNoFuso,
  gradeDaSemana,
  horaNoFuso,
  horaParaMinutos,
  instanteDe,
  limitesDaSemana,
  minutosParaHora,
  motivoDaAgendaIndisponivel,
  papelNaAgenda,
  podeOperarOAtendimento,
  rotuloDoStatus,
  semanaDe,
  traduzirMotivo,
} from "../../lib/agenda-interna";

/** Uma lista pedida ao servidor: ainda não lida, lida, ou falhou com motivo.
 *  Falha de leitura NUNCA vira lista vazia (regra do acervo de relatórios). */
type Lista<T> = { estado: "carregando" } | { estado: "ok"; itens: T[] } | { estado: "falhou"; motivo: string };

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
 * profissional — o supervisor recebe identificadores. Em 20/10/2026 (revisão
 * pré-fase 5): o clínico vê o nome só dos SEUS pacientes.
 */
export function AgendaInterna({ modo }: { modo: "clinica" | "propria" }) {
  const [capacidades, setCapacidades] = useState<EstadoV2<CapacidadesPsiqueV2>>({
    estado: "indisponivel",
    motivo: "CARREGANDO",
  });
  const [clinicos, setClinicos] = useState<Lista<ClinicoV2>>({ estado: "carregando" });
  const [pacientes, setPacientes] = useState<Lista<PacienteV2>>({ estado: "carregando" });
  const [recorteDeNomes, setRecorteDeNomes] = useState<"all" | "own" | "none">("all");
  const [agendamentos, setAgendamentos] = useState<AgendamentoV2[]>([]);
  const [referencia, setReferencia] = useState(() => new Date());
  const [aviso, setAviso] = useState("");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [editando, setEditando] = useState<AgendamentoV2 | null>(null);
  const [cancelando, setCancelando] = useState<AgendamentoV2 | null>(null);
  const [motivoDoCancelamento, setMotivoDoCancelamento] = useState("");
  const [form, setForm] = useState({ clinico: "", paciente: "", dia: diaIso(new Date()), hora: "09:00", duracao: "50" });
  const [disponibilidade, setDisponibilidade] = useState({ clinico: "", weekday: "1", inicio: "08:00", fim: "18:00" });

  const dias = useMemo(() => semanaDe(referencia), [referencia]);
  const papel = useMemo(() => papelNaAgenda(capacidades), [capacidades]);
  const listaDeClinicos = clinicos.estado === "ok" ? clinicos.itens : [];
  const listaDePacientes = pacientes.estado === "ok" ? pacientes.itens : [];
  // O clínico é reconhecido pelo vínculo (membership_id) que o servidor
  // devolve nas capacidades. Até 20/10/2026 era por igualdade de e-mail, e
  // um alias ou e-mail ausente deixava o clínico sem agenda e sem causa.
  const clinicoProprio = useMemo(
    () => (papel?.membershipId ? listaDeClinicos.find((c) => c.membership_id === papel.membershipId) || null : null),
    [listaDeClinicos, papel],
  );
  const clinicosVisiveis = useMemo(
    () => (modo === "propria" ? (clinicoProprio ? [clinicoProprio] : []) : listaDeClinicos),
    [modo, listaDeClinicos, clinicoProprio],
  );
  const podeOperarTodos = Boolean(papel?.geral) && modo === "clinica";
  const grade = useMemo(() => gradeDaSemana(agendamentos, dias, FUSO_PADRAO), [agendamentos, dias]);
  const rotuloDoPaciente = useCallback(
    (item: AgendamentoV2) =>
      item.patient_name ||
      listaDePacientes.find((p) => p.patient_id === item.patient_id)?.label ||
      `Paciente ${item.patient_id.slice(-4)}`,
    [listaDePacientes],
  );

  const carregarAgenda = useCallback(async () => {
    // Os limites da semana no fuso da agenda, nao no do navegador: ate
    // 20/10/2026 eram meia-noite local, e um navegador fora de Sao Paulo
    // pedia uma janela deslocada enquanto a grade era montada em Sao Paulo.
    const { inicio, fim } = limitesDaSemana(dias, FUSO_PADRAO);
    const resposta = await listarAgendaV2(inicio, fim);
    if (resposta.estado === "ok") {
      setAgendamentos(resposta.dados.appointments);
      setErro("");
    } else {
      setAgendamentos([]);
      setErro(`A agenda não pôde ser lida: ${traduzirMotivo(resposta.motivo)}.`);
    }
  }, [dias]);

  const carregarClinicos = useCallback(async () => {
    const r = await listarClinicosV2();
    setClinicos(r.estado === "ok" ? { estado: "ok", itens: r.dados.clinicians } : { estado: "falhou", motivo: r.motivo });
  }, []);

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
      setClinicos(r.estado === "ok" ? { estado: "ok", itens: r.dados.clinicians } : { estado: "falhou", motivo: r.motivo });
    });
    void listarPacientesV2().then((r) => {
      if (!ativo) return;
      if (r.estado === "ok") {
        setPacientes({ estado: "ok", itens: r.dados.patients });
        setRecorteDeNomes(r.dados.names_scope || (r.dados.with_names ? "all" : "none"));
      } else {
        setPacientes({ estado: "falhou", motivo: r.motivo });
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
    } else if (!form.clinico && listaDeClinicos[0]) {
      setForm((f) => ({ ...f, clinico: listaDeClinicos[0].membership_id }));
      setDisponibilidade((d) => ({ ...d, clinico: listaDeClinicos[0].membership_id }));
    }
  }, [modo, clinicoProprio, listaDeClinicos, form.clinico]);

  useEffect(() => {
    // A agenda recarregada traz a versao nova: o item em edicao acompanha,
    // para o proximo "Confirmar" nao partir de uma versao vencida.
    if (!editando) return;
    const atual = agendamentos.find((a) => a.appointment_id === editando.appointment_id);
    if (atual && atual.version !== editando.version) setEditando(atual);
  }, [agendamentos, editando]);

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
        if (r.estado === "ok" && r.dados.applied) {
          setAviso("Atendimento reagendado.");
          setEditando(null);
        } else {
          // Recusado (versao vencida, conflito): continua em edicao. Ate
          // 20/10/2026 saia do modo edicao com o formulario cheio, e o clique
          // seguinte CRIAVA um segundo atendimento.
          setErro(`Não reagendado: ${traduzirMotivo(r.estado === "ok" ? r.dados.code || "recusado" : r.motivo)}. O atendimento original continua marcado.`);
        }
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

  const prepararCancelamento = (item: AgendamentoV2) => {
    setAviso("");
    setErro("");
    setEditando(null);
    setCancelando(item);
    setMotivoDoCancelamento("");
  };

  const confirmarCancelamento = async () => {
    // Sem `window.confirm` (bloqueante e sem motivo) e sem clique duplo: o
    // botao fica desativado enquanto a chamada pende.
    if (!cancelando || salvando) return;
    const motivoInformado = motivoDoCancelamento.trim();
    if (!motivoInformado) {
      setErro("Informe o motivo do cancelamento.");
      return;
    }
    setSalvando(true);
    setErro("");
    try {
      const r = await cancelarAgendamentoV2(cancelando.appointment_id, {
        expected_version: cancelando.version,
        reason: motivoInformado,
      });
      if (r.estado === "ok" && r.dados.applied) {
        setAviso("Atendimento cancelado.");
        setCancelando(null);
      } else {
        setErro(`Não cancelado: ${traduzirMotivo(r.estado === "ok" ? r.dados.code || "recusado" : r.motivo)}.`);
      }
      await carregarAgenda();
    } finally {
      setSalvando(false);
    }
  };

  const prepararReagendamento = (item: AgendamentoV2) => {
    setCancelando(null);
    setEditando(item);
    setForm((f) => ({
      ...f,
      clinico: item.clinician_membership_id,
      paciente: item.patient_id,
      dia: diaNoFuso(item.start_at, FUSO_PADRAO),
      hora: horaNoFuso(item.start_at, FUSO_PADRAO),
      duracao: String(Math.round((new Date(item.end_at).getTime() - new Date(item.start_at).getTime()) / 60000)),
    }));
    setAviso("Ajuste dia, hora ou duração e confirme o reagendamento.");
  };

  const salvarDisponibilidade = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setAviso("");
    setErro("");
    const inicio = horaParaMinutos(disponibilidade.inicio);
    const fim = horaParaMinutos(disponibilidade.fim);
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
      await carregarClinicos();
    } else {
      setErro(`Disponibilidade não salva: ${traduzirMotivo(r.motivo)}.`);
    }
  };

  const mover = (semanas: number) =>
    setReferencia((r) => new Date(r.getFullYear(), r.getMonth(), r.getDate() + 7 * semanas));

  const linhaVazia = (() => {
    if (clinicos.estado === "carregando") return "Lendo os clínicos da clínica...";
    if (clinicos.estado === "falhou") return `Os clínicos não puderam ser lidos: ${traduzirMotivo(clinicos.motivo)}.`;
    if (modo === "propria" && !clinicoProprio) {
      return papel?.membershipId
        ? "Seu vínculo tem papel de clínico, mas não está na lista de clínicos desta clínica. Peça à administração para conferir."
        : "O servidor não informou o seu vínculo nesta clínica; a agenda própria não pôde ser montada.";
    }
    if (clinicosVisiveis.length === 0) return "Nenhum clínico com papel V2 nesta clínica ainda.";
    return "";
  })();

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
        {recorteDeNomes === "none" ? " Você vê identificadores, não nomes de pacientes." : ""}
        {recorteDeNomes === "own" ? " Você vê o nome dos seus pacientes; os demais, por identificador." : ""}
      </p>

      {aviso ? <p data-campo="aviso" className="mt-2 text-xs text-cyan-200">{aviso}</p> : null}
      {erro ? <p data-campo="erro" role="alert" className="mt-2 text-xs text-red-300">{erro}</p> : null}
      {pacientes.estado === "falhou" ? (
        <p data-campo="pacientes-nao-lidos" role="alert" className="mt-2 text-xs text-amber-200">
          Os pacientes não puderam ser lidos: {traduzirMotivo(pacientes.motivo)}. Sem a lista não dá para marcar.
        </p>
      ) : null}

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
            {linhaVazia ? (
              <tr>
                <td colSpan={8} data-campo="sem-clinicos" className="px-2 py-3 text-slate-500">
                  {linhaVazia}
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
                      {itens.map((item) => {
                        const operavel = podeOperarOAtendimento(item.appointment_status);
                        const seu = podeOperarTodos || item.clinician_membership_id === clinicoProprio?.membership_id;
                        const emCancelamento = cancelando?.appointment_id === item.appointment_id;
                        return (
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
                            <p className="text-[9px] uppercase text-slate-400">{rotuloDoStatus(item.appointment_status)}</p>
                            {operavel && seu && !emCancelamento ? (
                              <div className="mt-1 flex gap-1">
                                <button type="button" disabled={salvando} onClick={() => prepararReagendamento(item)} className="rounded border border-slate-700 px-1 text-[9px] hover:bg-slate-800 disabled:opacity-60">
                                  reagendar
                                </button>
                                <button type="button" disabled={salvando} onClick={() => prepararCancelamento(item)} className="rounded border border-red-900 px-1 text-[9px] text-red-300 hover:bg-red-950 disabled:opacity-60">
                                  cancelar
                                </button>
                              </div>
                            ) : null}
                            {emCancelamento ? (
                              <div data-campo="confirmar-cancelamento" className="mt-1 flex flex-col gap-1">
                                <input
                                  type="text"
                                  value={motivoDoCancelamento}
                                  onChange={(e) => setMotivoDoCancelamento(e.target.value)}
                                  placeholder="motivo do cancelamento"
                                  className="rounded border border-slate-700 bg-slate-900 px-1 py-0.5 text-[10px]"
                                />
                                <div className="flex gap-1">
                                  <button type="button" disabled={salvando} onClick={() => void confirmarCancelamento()} className="rounded bg-red-800 px-1 text-[9px] font-bold text-white hover:bg-red-900 disabled:opacity-60">
                                    {salvando ? "cancelando..." : "confirmar cancelamento"}
                                  </button>
                                  <button type="button" disabled={salvando} onClick={() => setCancelando(null)} className="rounded border border-slate-700 px-1 text-[9px] hover:bg-slate-800 disabled:opacity-60">
                                    desistir
                                  </button>
                                </div>
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
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
            disabled={Boolean(editando) || pacientes.estado !== "ok"}
            onChange={(e) => setForm((f) => ({ ...f, paciente: e.target.value }))}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1"
          >
            <option value="">
              {pacientes.estado === "carregando" ? "lendo..." : pacientes.estado === "falhou" ? "lista não lida" : "escolha"}
            </option>
            {listaDePacientes.map((p) => (
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
