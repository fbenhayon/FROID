// Espelho do Portão A para as telas que precisam avisar ANTES de existir
// campanha.
//
// A decisão de liberar resultado é sempre do SQL (froid_nr1_required_sample, em
// migrations/025) e o painel lê o veredito pronto do servidor. Este arquivo
// existe para um caso diferente: o cadastro da empresa, onde a pessoa digita o
// efetivo de uma unidade e precisa saber ali mesmo se aquele número produz
// recorte — antes de montar setores em cima de uma unidade que nunca vai
// publicar. Descobrir isso no fim é a conversa ruim que o cadastro existe para
// evitar.
//
// Por isso os três parâmetros são repetidos aqui em vez de buscados: eles são
// dado em gro_risk_criteria e podem variar por organização, mas no cadastro
// ainda não há organização de onde lê-los. O aviso é estimativa; quem decide é
// o banco.

/**
 * Pisos de anonimato. O de recorte vem da migration 010; o de campanha foi
 * redefinido na 027 e vale a última definição.
 *
 * Eles não protegem a mesma coisa. PISO_RECORTE protege pessoa: é ele que
 * decide o tamanho mínimo de cada coorte publicada, e por isso não se move.
 * PISO_CAMPANHA diz quanta resposta a campanha precisa somar — e desde que a
 * representatividade entrou, era ela, não este piso, que barrava campanha
 * rala em empresa grande.
 */
export const PISO_CAMPANHA = 15;
export const PISO_RECORTE = 10;

/** Parâmetros de amostragem padrão da plataforma (migration 025). */
export const AMOSTRA_Z = 1.96;
export const AMOSTRA_MARGEM = 0.05;
export const AMOSTRA_CORTE_CENSO = 0.8;

/**
 * Respostas substantivas necessárias para uma coorte falar por `populacao`.
 *
 * Amostra para proporção com correção de população finita, em p=0,5 — a
 * proporção de maior variância, e portanto a exigência conservadora qualquer
 * que seja o resultado medido.
 *
 * Devolve null quando o efetivo não foi declarado: sem denominador não existe
 * "amostra suficiente", e devolver zero faria do efetivo não declarado o
 * caminho mais curto para desligar o portão.
 */
export function amostraNecessaria(
  populacao: number,
  margem = AMOSTRA_MARGEM,
  z = AMOSTRA_Z,
  corteCenso = AMOSTRA_CORTE_CENSO,
): number | null {
  if (!Number.isFinite(populacao) || populacao <= 0) return null;
  const semLimite = (z * z) * 0.25 / (margem * margem);
  const corrigido = semLimite / (1 + (semLimite - 1) / populacao);
  // A transição para censo é decidida sobre o valor CONTÍNUO, antes do teto.
  // Comparando o inteiro já arredondado, o arredondamento empurra populações
  // logo acima do corte para o outro lado e a exigência oscila: 100 pessoas
  // pedindo amostra de 80, 101 pedindo censo de 101, 102 pedindo amostra de
  // novo. Quem tivesse 101 no quadro pagaria por declarar uma pessoa a mais.
  if (corrigido > corteCenso * populacao) return populacao;
  // Arredondar antes do teto para que 80,0000000001 — ruído da divisão, não
  // exigência — não vire 81 respostas.
  return Math.min(populacao, Math.ceil(Math.round(corrigido * 1e9) / 1e9));
}

/** Respostas que uma unidade precisa para publicar recorte próprio. */
export function exigidoNoRecorte(efetivo: number): number | null {
  const amostra = amostraNecessaria(efetivo);
  if (amostra === null) return null;
  return Math.max(PISO_RECORTE, amostra);
}

/** Respostas que a campanha inteira precisa para liberar qualquer resultado. */
export function exigidoNaCampanha(efetivo: number): number | null {
  const amostra = amostraNecessaria(efetivo);
  if (amostra === null) return null;
  return Math.max(PISO_CAMPANHA, amostra);
}

/** A unidade só publica se todo mundo responder. */
export function exigeCenso(efetivo: number): boolean {
  const amostra = amostraNecessaria(efetivo);
  return amostra !== null && amostra >= efetivo;
}

/**
 * Que caminho de conformidade o porte declarado sustenta.
 *
 * Não é uma escala de qualidade: os três são conformes. É que a NR-1 não
 * prescreve metodologia, e o questionário só descreve a exposição quando há
 * coorte para isso. Abaixo de 15 respostas nenhuma campanha publica, por mais
 * adesão que haja. De 15 a 97 publica, mas só em censo: nesse tamanho a fórmula
 * de amostra pede todo mundo, então falta uma resposta e o recorte não sai — e
 * responder continua sendo voluntário, o que faz do censo uma meta e não uma
 * garantia. De 98 em diante a amostra passa a economizar respostas, e a partir
 * dali sobra folga entre quem responde e quem precisa responder.
 *
 * Em todos eles a AEP continua obrigatória: o MTE é explícito que questionário
 * não comprova gestão de risco isoladamente, e ME/EPP dispensadas de PGR não
 * são dispensadas da AEP. O que muda é se a campanha entra como insumo dela ou
 * se a AEP caminha sozinha.
 */
export type CaminhoDoPorte = "aep" | "censo" | "campanha";

export function caminhoDoPorte(efetivo: number): CaminhoDoPorte {
  if (!Number.isFinite(efetivo) || efetivo < PISO_CAMPANHA) return "aep";
  return exigeCenso(efetivo) ? "censo" : "campanha";
}
