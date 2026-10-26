/**
 * As contas puras da agenda interna: semana, instantes com fuso, grade e
 * papéis. Separadas do componente para serem testadas sem React.
 *
 * O servidor é a autoridade (dupla marcação impossível no banco, papéis
 * checados lá); aqui só se monta o que a tela mostra e o que ela envia.
 */

import type { AgendamentoV2, CapacidadesPsiqueV2, EstadoV2 } from "./psique-v2-api";

export const FUSO_PADRAO = "America/Sao_Paulo";
export const DIAS_DA_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

/** Os sete dias da semana de `data`, começando na segunda-feira, à meia-noite local. */
export function semanaDe(data: Date): Date[] {
  const base = new Date(data.getFullYear(), data.getMonth(), data.getDate());
  const recuo = (base.getDay() + 6) % 7; // segunda = 0
  const segunda = new Date(base.getFullYear(), base.getMonth(), base.getDate() - recuo);
  return Array.from({ length: 7 }, (_, i) => new Date(segunda.getFullYear(), segunda.getMonth(), segunda.getDate() + i));
}

/** yyyy-mm-dd de uma data local. */
export function diaIso(data: Date): string {
  const m = String(data.getMonth() + 1).padStart(2, "0");
  const d = String(data.getDate()).padStart(2, "0");
  return `${data.getFullYear()}-${m}-${d}`;
}

/** "08:00" a partir de minutos desde a meia-noite. */
export function minutosParaHora(minutos: number): string {
  const total = Math.max(0, Math.floor(minutos));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/** Minutos desde a meia-noite de "HH:MM"; null se não for hora. */
export function horaParaMinutos(hora: string): number | null {
  const partes = /^(\d{1,2}):(\d{2})$/.exec(String(hora || "").trim());
  if (!partes) return null;
  const h = Number(partes[1]);
  const m = Number(partes[2]);
  if (h > 23 || m > 59) return null;
  return h * 60 + m;
}

/** Deslocamento (minutos) de `fuso` em relação ao UTC num dado instante. */
function deslocamento(instante: Date, fuso: string): number {
  const partes = new Intl.DateTimeFormat("en-US", {
    timeZone: fuso,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(instante);
  const valor = (tipo: string) => Number(partes.find((p) => p.type === tipo)?.value || "0");
  const comoUtc = Date.UTC(valor("year"), valor("month") - 1, valor("day"), valor("hour"), valor("minute"), valor("second"));
  return Math.round((comoUtc - instante.getTime()) / 60000);
}

/** O instante (ISO, UTC) de um dia e hora de relógio num fuso IANA.
 *
 *  Duas passagens resolvem o horário de verão: a primeira estima o
 *  deslocamento, a segunda confere no instante encontrado. */
export function instanteDe(dia: string, hora: string, fuso: string): string | null {
  const minutos = horaParaMinutos(hora);
  const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dia);
  if (minutos === null || !partes) return null;
  const ano = Number(partes[1]);
  const mes = Number(partes[2]);
  const diaDoMes = Number(partes[3]);
  // "2027-13-01" passa no formato e não é um dia: a volta pelo calendário diz.
  const conferido = new Date(Date.UTC(ano, mes - 1, diaDoMes));
  if (conferido.getUTCFullYear() !== ano || conferido.getUTCMonth() !== mes - 1 || conferido.getUTCDate() !== diaDoMes) {
    return null;
  }
  const relogioUtc = Date.UTC(ano, mes - 1, diaDoMes, Math.floor(minutos / 60), minutos % 60);
  let estimado = new Date(relogioUtc - deslocamento(new Date(relogioUtc), fuso) * 60000);
  estimado = new Date(relogioUtc - deslocamento(estimado, fuso) * 60000);
  return estimado.toISOString();
}

/** A janela [inicio, fim) da semana `dias` como instantes no fuso dado:
 *  meia-noite do primeiro dia e meia-noite do dia seguinte ao ultimo. */
export function limitesDaSemana(dias: Date[], fuso: string): { inicio: string; fim: string } {
  const ultimo = dias[dias.length - 1];
  const seguinte = new Date(ultimo.getFullYear(), ultimo.getMonth(), ultimo.getDate() + 1);
  const inicio = instanteDe(diaIso(dias[0]), "00:00", fuso);
  const fim = instanteDe(diaIso(seguinte), "00:00", fuso);
  if (!inicio || !fim) throw new Error("semana sem dias validos");
  return { inicio, fim };
}

/** "HH:MM" de um instante ISO, no fuso dado. */
export function horaNoFuso(iso: string, fuso: string): string {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "--:--";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: fuso, hourCycle: "h23", hour: "2-digit", minute: "2-digit" }).format(data);
}

/** yyyy-mm-dd de um instante ISO, no fuso dado. */
export function diaNoFuso(iso: string, fuso: string): string {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "";
  const partes = new Intl.DateTimeFormat("en-CA", { timeZone: fuso, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(data);
  const valor = (tipo: string) => partes.find((p) => p.type === tipo)?.value || "";
  return `${valor("year")}-${valor("month")}-${valor("day")}`;
}

/** Os agendamentos de cada clínico em cada dia da semana, em ordem de início. */
export function gradeDaSemana(
  agendamentos: AgendamentoV2[],
  dias: Date[],
  fuso: string,
): Map<string, Map<string, AgendamentoV2[]>> {
  const grade = new Map<string, Map<string, AgendamentoV2[]>>();
  const chaves = new Set(dias.map(diaIso));
  const ordenados = [...agendamentos].sort((a, b) => a.start_at.localeCompare(b.start_at));
  for (const item of ordenados) {
    const dia = diaNoFuso(item.start_at, fuso);
    if (!chaves.has(dia)) continue;
    const porDia = grade.get(item.clinician_membership_id) || new Map<string, AgendamentoV2[]>();
    porDia.set(dia, [...(porDia.get(dia) || []), item]);
    grade.set(item.clinician_membership_id, porDia);
  }
  return grade;
}

export type PapelNaAgenda = {
  /** Vê e opera a agenda de todos: secretária, administrador, supervisor. */
  geral: boolean;
  /** É clínico: tem agenda própria. */
  clinico: boolean;
  /** Recebe o nome dos pacientes (o supervisor não; o clínico, só dos seus). */
  veNomes: boolean;
  /** O vínculo desta pessoa na organização, como o servidor o devolve; é por
   *  ele que a agenda própria reconhece o clínico (não por e-mail). */
  membershipId: string | null;
};

/** O que esta pessoa pode na agenda, a partir das capacidades do servidor. */
export function papelNaAgenda(capacidades: EstadoV2<CapacidadesPsiqueV2>): PapelNaAgenda | null {
  if (capacidades.estado !== "ok" || capacidades.dados.rbac_version !== 2) return null;
  const papeis = new Set(capacidades.dados.v2_roles || []);
  const staff = papeis.has("SECRETARY") || papeis.has("ORG_ADMIN");
  const supervisor = papeis.has("CLINICAL_SUPERVISOR");
  return {
    geral: staff || supervisor,
    clinico: papeis.has("CLINICIAN"),
    veNomes: staff || papeis.has("CLINICIAN"),
    membershipId: String(capacidades.dados.membership_id || "") || null,
  };
}

/** O servidor sem a rota V2 responde 404: é o único motivo que significa
 *  "não ligada". Qualquer outro é uma leitura que falhou, e a frase diz qual. */
export const MOTIVO_DE_ROTA_AUSENTE = "HTTP_404";

/** A frase que a tela mostra quando a agenda não está disponível.
 *
 *  Até 20/10/2026 todo `indisponivel` virava "não está ligada neste servidor"
 *  (um 500 ou a rede caída liam-se como configuração), e `negado` descartava
 *  o motivo. Cada causa pede uma ação diferente de quem lê. */
export function motivoDaAgendaIndisponivel(capacidades: EstadoV2<CapacidadesPsiqueV2>): string {
  if (capacidades.estado === "negado") {
    return `Sem permissão para a agenda nesta organização: ${traduzirMotivo(capacidades.motivo)}.`;
  }
  if (capacidades.estado === "indisponivel") {
    if (capacidades.motivo === "CARREGANDO") return "Carregando a agenda...";
    if (capacidades.motivo === MOTIVO_DE_ROTA_AUSENTE) return "A agenda interna não está ligada neste servidor.";
    return `A agenda não pôde ser lida: ${traduzirMotivo(capacidades.motivo)}.`;
  }
  if (capacidades.dados.rbac_version !== 2) {
    return "Esta clínica ainda não ativou os papéis V2. O responsável ativa em Gestão da clínica, em Papéis e agenda.";
  }
  const papel = papelNaAgenda(capacidades);
  if (papel && !papel.geral && !papel.clinico) {
    return "Seu papel nesta clínica não inclui agenda. Peça ao responsável um papel de clínico, secretaria ou supervisão.";
  }
  return "";
}

/** Os status do atendimento (domínio da migration 044) na língua da tela. */
const ROTULO_DO_STATUS: Record<string, string> = {
  SCHEDULED: "marcado",
  CONFIRMED: "confirmado",
  IN_PROGRESS: "em atendimento",
  COMPLETED: "realizado",
  CANCELLED: "cancelado",
  NO_SHOW: "não compareceu",
};

/** O status como a tela o escreve; um status desconhecido sai como veio,
 *  para não esconder um valor novo do servidor. */
export function rotuloDoStatus(status: string): string {
  return ROTULO_DO_STATUS[status] || status;
}

/** Só o que ainda vai acontecer se reagenda ou cancela. Até 20/10/2026 os
 *  botões apareciam também em realizado e não compareceu. */
export function podeOperarOAtendimento(status: string): boolean {
  return status === "SCHEDULED" || status === "CONFIRMED";
}

/** Os códigos do servidor que a tela sabe explicar; o resto sai como veio. */
export function traduzirMotivo(codigo: string): string {
  const frases: Record<string, string> = {
    APPOINTMENT_CONFLICT: "o clínico já tem atendimento nesse horário",
    OUTSIDE_AVAILABILITY: "fora da disponibilidade cadastrada do clínico",
    OWN_AGENDA_ONLY: "você só pode operar a sua própria agenda",
    OWN_AVAILABILITY_ONLY: "você só pode definir a sua própria disponibilidade",
    APPOINTMENT_PATIENT_REQUIRED: "o paciente não está ativo nesta clínica",
    APPOINTMENT_CLINICIAN_REQUIRED: "a pessoa escolhida não tem papel de clínico",
    APPOINTMENT_VERSION_MISMATCH: "o atendimento mudou desde que a tela o leu; ela foi recarregada",
    APPOINTMENT_NOT_FOUND: "o atendimento não existe mais",
    RBAC_V2_NOT_ENABLED: "a clínica ainda não ativou os papéis V2",
    PSIQUE_SCHEDULING_ROLE_DENIED: "seu papel não inclui agenda",
    SEM_CONEXAO: "sem conexão com o servidor",
    RESPOSTA_ILEGIVEL: "o servidor respondeu algo que a tela não entendeu",
    HTTP_401: "sua sessão de trabalho expirou; entre de novo",
    HTTP_403: "sem permissão nesta organização",
    HTTP_500: "o servidor falhou ao responder",
    HTTP_502: "o servidor não respondeu",
    HTTP_503: "o servidor está indisponível no momento",
  };
  return frases[codigo] || codigo;
}
