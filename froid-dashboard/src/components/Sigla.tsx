import React from "react";
import { descricao, SIGLAS } from "../lib/nr1-glossario";

/**
 * Uma sigla que se explica sozinha.
 *
 * Renderiza `<abbr>`, que é o elemento que existe exatamente para isto: o
 * navegador mostra o significado ao passar o mouse, o leitor de tela anuncia a
 * expansão, e o texto continua curto para quem já conhece a sigla.
 *
 * O sublinhado pontilhado não é enfeite — é a convenção que sinaliza "há algo
 * a revelar aqui". Sem ele a explicação existe e ninguém descobre que existe.
 *
 * Em tela sensível ao toque não há "passar o mouse". Por isso a primeira
 * aparição de cada sigla numa tela deve usar `porExtenso()`, e não este
 * componente: quem lê no celular precisa da expansão escrita.
 */
export const Sigla: React.FC<{ nome: string; className?: string }> = ({
  nome,
  className,
}) => {
  if (!SIGLAS[nome]) return <>{nome}</>;
  return (
    <abbr
      title={descricao(nome)}
      className={
        className ??
        "cursor-help underline decoration-dotted underline-offset-2"
      }
    >
      {nome}
    </abbr>
  );
};

export default Sigla;
