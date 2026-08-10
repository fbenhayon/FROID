/**
 * A frase de abertura do relatório que o paciente recebe.
 *
 * São cinco, sorteadas a cada documento. O rodízio tem uma consequência que
 * define a escrita: como o paciente recebe UMA, cada variante precisa carregar
 * sozinha as duas salvaguardas. Não existe "a versão mais protegida" — a que
 * saiu é a única que aquela pessoa vai ler.
 *
 *   1. Aponta para o profissional. É ele quem interpreta, e o documento existe
 *      para alimentar a próxima conversa, não para encerrar o assunto.
 *   2. Diz que não é conclusão sobre a pessoa. O paciente lê isso sozinho,
 *      provavelmente à noite, sem ninguém para contextualizar.
 *
 * O objetivo declarado — perceber novas possibilidades na leitura de fatores
 * psíquicos, e fazer disso uma prática de reconhecimento pessoal — aparece em
 * todas, com palavras diferentes.
 */

export const REPORT_INTROS: readonly string[] = [
  // A — convite
  "Este relatório existe para abrir possibilidades. Ao reunir o que foi "
  + "observado durante a sessão, ele oferece à sua saúde mental uma prática de "
  + "reconhecimento pessoal — não um retrato de quem você é, mas um registro do "
  + "que se moveu nesta conversa. Cada observação aqui é ponto de partida para "
  + "o diálogo com o seu profissional, que conhece o contexto que os números "
  + "não alcançam.",

  // B — prática
  "O propósito deste documento é transformar percepção em prática. Os sinais "
  + "reunidos apontam fatores psíquicos que merecem atenção e sustentam um "
  + "exercício contínuo de reconhecimento pessoal — a base sobre a qual a saúde "
  + "mental se constrói. Nada aqui conclui algo sobre você: a leitura destes "
  + "registros pertence ao seu profissional, junto com você.",

  // C — sóbria
  "Este relatório reúne o que foi observado durante a sessão com um objetivo "
  + "declarado: ampliar a percepção sobre fatores psíquicos e favorecer uma "
  + "prática de reconhecimento pessoal. O que está descrito aqui é ponto de "
  + "partida para o diálogo com o seu profissional, nunca conclusão sobre você.",

  // D — ampla
  "Perceber mais é poder escolher melhor. Este documento localiza fatores "
  + "psíquicos que emergiram durante a sessão e os devolve como possibilidades — "
  + "matéria para uma prática de reconhecimento pessoal que sustenta a saúde "
  + "mental ao longo do tempo. São observações para conversar com o seu "
  + "profissional, e não afirmações sobre quem você é.",

  // E — curta
  "Este relatório serve a uma intenção: perceber novas possibilidades na "
  + "leitura dos fatores psíquicos, e fazer dessa percepção uma prática de "
  + "reconhecimento pessoal a serviço da sua saúde mental. O que está aqui "
  + "abre conversa com o seu profissional — não fecha conclusão sobre você.",
] as const;

/**
 * Sorteia a frase de abertura.
 *
 * A semente opcional existe para o teste: sorteio verdadeiro num teste produz
 * reprovação intermitente, que é pior do que teste nenhum porque ensina a
 * ignorar falha.
 */
export function pickIntro(seed?: number): string {
  const indice =
    typeof seed === "number" && Number.isFinite(seed)
      ? Math.abs(Math.trunc(seed)) % REPORT_INTROS.length
      : Math.floor(Math.random() * REPORT_INTROS.length);
  return REPORT_INTROS[indice] ?? REPORT_INTROS[REPORT_INTROS.length - 1];
}
