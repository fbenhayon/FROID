/**
 * O caminho do convite de sessão, escrito uma vez só.
 *
 * Não se "abre" uma sessão de um paciente pelo painel: convida-se. Quem convida
 * cai no formulário de cadastro/convite (`/patients/new`) já preenchido com o
 * que se sabe da pessoa, e é lá que o link único e a mensagem de WhatsApp são
 * gerados.
 *
 * Três telas convidam — dashboard detalhado, dashboard resumido e ficha do
 * paciente — e a rota tem parâmetros casados por NOME com o que `NewPatient` lê
 * em `searchParams`. Montar essa query string em cada tela é o espelho de nome
 * da seção 2.9: escrever `telefone` onde o leitor espera `phone` não dá erro
 * nenhum — abre o formulário em branco, e quem convidou não tem como saber que
 * o preenchimento se perdeu. Por isso o produtor é um só.
 */

export type PacienteConvidavel = {
  name?: string;
  email?: string;
  phone?: string;
};

/**
 * `captureMode` só existe para a sessão presencial em que o celular do paciente
 * vira câmera; o convite remoto comum não o envia.
 */
export function caminhoDoConviteDeSessao(
  patient?: PacienteConvidavel | null,
  captureMode?: "patient_mobile",
): string {
  const params = new URLSearchParams();
  if (patient?.name) params.set("name", patient.name);
  if (patient?.email) params.set("email", patient.email);
  if (patient?.phone) params.set("phone", patient.phone);
  if (captureMode) params.set("capture", captureMode);
  const query = params.toString();
  return `/patients/new${query ? `?${query}` : ""}`;
}
