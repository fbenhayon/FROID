/**
 * A citação de abertura do relatório do profissional.
 *
 * Dirigida a quem faz o trabalho: pesquisar, insistir na compreensão entre
 * pessoas, procurar caminho novo quando o conhecido não alcança. Sorteada a
 * cada documento, como as aberturas do relatório do paciente.
 *
 * SOBRE A ATRIBUIÇÃO, que aqui não é detalhe.
 *
 * Einstein e Gandhi são os autores mais mal citados da história — "seja a
 * mudança que você quer ver no mundo" e "a mente que se abre a uma nova ideia
 * jamais volta ao tamanho original" NÃO são deles, e circulam como se fossem.
 * Um relatório clínico que vai para prontuário não é lugar para frase apócrifa:
 * uma atribuição falsa num documento assinado contamina a credibilidade de
 * tudo o mais que está nele.
 *
 * Cada frase abaixo tem fonte declarada e verificável. Quem acrescentar uma
 * sexta precisa fazer o mesmo — o campo `fonte` não é decorativo.
 */

export type Epigraph = {
  texto: string;
  autor: string;
  /** Obra, discurso ou publicação. Nunca vazio. */
  fonte: string;
};

export const REPORT_EPIGRAPHS: readonly Epigraph[] = [
  {
    texto: "Sabemos o que somos, mas não o que podemos ser.",
    autor: "William Shakespeare",
    fonte: "Hamlet, ato IV, cena V",
  },
  {
    texto: "O importante é não parar de questionar.",
    autor: "Albert Einstein",
    fonte: "Entrevista à revista LIFE, 1955",
  },
  {
    texto:
      "A regra de ouro da conduta é a tolerância mútua, "
      + "visto que nunca pensaremos todos da mesma forma.",
    autor: "Mohandas Gandhi",
    fonte: "Young India, 1920",
  },
  {
    texto:
      "Pegue um método e teste-o. Se falhar, admita com franqueza e tente "
      + "outro. Mas, acima de tudo, tente algo.",
    autor: "Franklin Delano Roosevelt",
    fonte: "Discurso na Oglethorpe University, 1932",
  },
  {
    texto:
      "Você pode fazer mais amigos em dois meses interessando-se pelos outros "
      + "do que em dois anos tentando que os outros se interessem por você.",
    autor: "Dale Carnegie",
    fonte: "Como Fazer Amigos e Influenciar Pessoas, 1936",
  },
] as const;

/** Semente opcional pelo mesmo motivo de report-intro: sorteio verdadeiro em
 *  teste produz reprovação intermitente, que ensina a ignorar falha. */
export function pickEpigraph(seed?: number): Epigraph {
  const indice =
    typeof seed === "number" && Number.isFinite(seed)
      ? Math.abs(Math.trunc(seed)) % REPORT_EPIGRAPHS.length
      : Math.floor(Math.random() * REPORT_EPIGRAPHS.length);
  return REPORT_EPIGRAPHS[indice] ?? REPORT_EPIGRAPHS[0];
}
