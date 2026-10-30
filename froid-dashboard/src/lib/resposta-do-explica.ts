/**
 * A resposta do FROID Explica separada em blocos: texto corrido e tabela.
 *
 * Desde a fase 3 (18/10/2026) o contrato de analise manda abrir com uma
 * tabela em markdown, uma linha por corte. O painel mostrava a resposta crua
 * em `whitespace-pre-wrap`, e uma tabela assim sairia como barras verticais
 * — o profissional leria "|" no lugar de colunas. Aqui as linhas que comecam
 * por "|" viram uma tabela; o resto segue como texto.
 *
 * Os asteriscos de negrito saem do texto: o contrato proibe rotulo em
 * negrito, e quando o modelo os poe mesmo assim eles so sujam a leitura.
 */
export type BlocoDaResposta =
  | { tipo: "texto"; texto: string }
  | { tipo: "tabela"; cabecalho: string[]; linhas: string[][] };

function celulas(linha: string): string[] {
  const miolo = linha.trim().replace(/^\|/, "").replace(/\|$/, "");
  // Os asteriscos de negrito saem tambem das celulas: ate 27/10/2026 so o
  // texto corrido era limpo, e "**IPM**" chegava a tela como cabecalho.
  return miolo.split("|").map((celula) => celula.replace(/\*\*/g, "").trim());
}

function ehSeparador(linha: string): boolean {
  return /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(linha.trim());
}

export function blocosDaResposta(texto: string): BlocoDaResposta[] {
  const linhas = String(texto || "").split("\n");
  const blocos: BlocoDaResposta[] = [];
  let textoAtual: string[] = [];
  let tabelaAtual: string[][] = [];

  const fechaTexto = () => {
    const corpo = textoAtual.join("\n").replace(/\*\*/g, "");
    if (corpo.trim()) blocos.push({ tipo: "texto", texto: corpo });
    textoAtual = [];
  };
  const fechaTabela = () => {
    if (tabelaAtual.length) {
      const [cabecalho, ...linhasDoCorpo] = tabelaAtual;
      blocos.push({ tipo: "tabela", cabecalho, linhas: linhasDoCorpo });
    }
    tabelaAtual = [];
  };

  for (const linha of linhas) {
    if (linha.trim().startsWith("|")) {
      if (textoAtual.length) fechaTexto();
      if (!ehSeparador(linha)) tabelaAtual.push(celulas(linha));
    } else {
      if (tabelaAtual.length) fechaTabela();
      textoAtual.push(linha);
    }
  }
  fechaTexto();
  fechaTabela();
  return blocos;
}
