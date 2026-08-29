// Histórico da consulta aberta e os prompts que o usuário salva.
//
// Por que existe como módulo separado, e não dentro da tela:
//
// A tela perdia a resposta anterior a cada nova pergunta — `setAberta(null)`
// no início de `perguntar`. Quem estava comparando duas respostas, ou tinha
// acabado de receber uma que ia copiar para um documento, perdia ao perguntar
// de novo. Numa demonstração ao vivo isso é constrangedor; no uso real é
// trabalho jogado fora.
//
// A regra de guarda também é diferente entre as duas coisas, e é por isso que
// elas usam armazenamentos distintos:
//
//   histórico -> sessionStorage. É o rastro do acesso de hoje. Fechou o
//                navegador, acabou. Ninguém quer reencontrar semana que vem a
//                pergunta que fez enquanto testava.
//   prompts   -> localStorage. É biblioteca: a pessoa salva a formulação que
//                funcionou para repetir no próximo ciclo.
//
// Ambos por organização. Quem opera uma carteira alterna entre organizações, e
// misturar o rastro de uma no painel de outra seria confuso na melhor das
// hipóteses.
//
// Nada aqui contém dado de trabalhador: a consulta aberta é sobre a norma, e o
// endpoint não recebe nem devolve resposta individual.

export type RespostaAberta = {
  disponivel: boolean;
  motivo?: string;
  resposta: string;
  citacoes: string[];
  motor?: string;
};

export type ItemHistorico = {
  id: string;
  pergunta: string;
  /** ISO. Serve para ordenar e para mostrar a hora ao lado da pergunta. */
  quando: string;
  resposta: RespostaAberta | null;
  /** Preenchido quando a consulta falhou. A pergunta entra no histórico
   *  mesmo assim: perdê-la é justamente o defeito que este módulo corrige. */
  erro?: string;
};

export type PromptSalvo = {
  id: string;
  titulo: string;
  texto: string;
};

/** Teto do histórico. Alto o bastante para uma sessão inteira de trabalho, e
 *  baixo o bastante para não estourar a cota do sessionStorage. */
export const LIMITE_HISTORICO = 50;
export const LIMITE_PROMPTS = 40;
export const TAMANHO_DO_TITULO = 64;

export const chaveHistorico = (organizationId: string): string =>
  `froid_nr1_explica_historico:${organizationId}`;

export const chavePrompts = (organizationId: string): string =>
  `froid_nr1_explica_prompts:${organizationId}`;

/** Título curto para o chip do prompt salvo. A primeira linha basta: quem
 *  escreveu a pergunta reconhece pelo começo dela. */
export function tituloDoPrompt(texto: string): string {
  const limpo = texto.trim().split("\n")[0].trim();
  if (limpo.length <= TAMANHO_DO_TITULO) return limpo;
  return `${limpo.slice(0, TAMANHO_DO_TITULO - 1).trimEnd()}…`;
}

/** Mais recente primeiro. É a ordem em que se procura o que acabou de sair. */
export function acrescentaAoHistorico(
  historico: ItemHistorico[],
  item: ItemHistorico,
): ItemHistorico[] {
  return [item, ...historico].slice(0, LIMITE_HISTORICO);
}

function mesmoTexto(a: string, b: string): boolean {
  return a.trim().replace(/\s+/g, " ") === b.trim().replace(/\s+/g, " ");
}

/** Salvar duas vezes a mesma pergunta não cria dois chips: promove o que já
 *  existe para o topo. Sem isto a biblioteca vira uma lista de repetições. */
export function salvaPrompt(
  prompts: PromptSalvo[],
  prompt: PromptSalvo,
): PromptSalvo[] {
  const semDuplicata = prompts.filter((p) => !mesmoTexto(p.texto, prompt.texto));
  return [prompt, ...semDuplicata].slice(0, LIMITE_PROMPTS);
}

export function removePrompt(prompts: PromptSalvo[], id: string): PromptSalvo[] {
  return prompts.filter((p) => p.id !== id);
}

export function jaSalvo(prompts: PromptSalvo[], texto: string): boolean {
  return prompts.some((p) => mesmoTexto(p.texto, texto));
}

/** Leitura tolerante.
 *
 *  O armazenamento falha de mais de um jeito: janela anônima que o bloqueia,
 *  cota estourada, e conteúdo de uma versão anterior que não casa mais com o
 *  tipo. Nenhum deles justifica quebrar a tela — o Explica precisa funcionar
 *  mesmo sem memória nenhuma. */
export function ler<T>(deposito: Storage | undefined, chave: string, padrao: T): T {
  try {
    const bruto = deposito?.getItem(chave);
    if (!bruto) return padrao;
    const valor = JSON.parse(bruto);
    return Array.isArray(padrao) && !Array.isArray(valor) ? padrao : (valor as T);
  } catch {
    return padrao;
  }
}

export function grava(deposito: Storage | undefined, chave: string, valor: unknown): void {
  try {
    deposito?.setItem(chave, JSON.stringify(valor));
  } catch {
    // Cota cheia ou armazenamento bloqueado. A sessão segue sem persistência.
  }
}

/** Identificador do item. `randomUUID` não existe em contexto sem HTTPS nem em
 *  navegador antigo, e aí o contador basta — ele só precisa ser único dentro
 *  desta lista, não no mundo. */
let sequencia = 0;
export function novoId(): string {
  const cripto = globalThis.crypto as Crypto | undefined;
  if (cripto?.randomUUID) return cripto.randomUUID();
  sequencia += 1;
  return `id-${sequencia}-${new Date().getTime()}`;
}
