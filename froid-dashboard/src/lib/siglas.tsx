// Como uma sigla aparece na tela. O QUE ela significa mora em nr1-glossario.
//
// Este arquivo nasceu com um dicionário próprio, e foi um erro: `nr1-glossario`
// já existia, mais completo e com nota explicativa por verbete. Ele não foi
// encontrado porque não tinha nenhum importador — o mesmo padrão que este
// módulo já produziu quatro vezes (desenho pronto, camada que ninguém chama), e
// que agora produziu uma consequência nova: em vez de a peça ficar parada, uma
// segunda foi construída ao lado dela.
//
// Duas definições da mesma sigla divergem sozinhas. A daqui foi removida.
//
// Três formas de apresentação, cada uma para um problema:
//
//   <Sigla nome="PGR" />          PGR (Programa de Gerenciamento de Riscos)
//   <Sigla nome="PGR" curta />    PGR — com a descrição no title, para as
//                                 repetições dentro do mesmo parágrafo, onde
//                                 expandir de novo faria o texto ilegível
//   <GlossarioDeSiglas termos={[...]} />  a lista ao pé da tela
//
// O glossário existe porque `title` é hover, e hover não existe em telefone.
// Ele é a garantia de que a denominação completa está VISÍVEL na tela, e não a
// um gesto de distância que metade dos leitores não tem.

import React from "react";

import { descricao, porExtenso, SIGLAS } from "./nr1-glossario";

export { SIGLAS } from "./nr1-glossario";

type SiglaProps = {
  nome: string;
  /** Repetição: mostra só a sigla, com a descrição no atributo `title`. */
  curta?: boolean;
  className?: string;
};

/** Uma sigla e o que ela quer dizer. */
export const Sigla: React.FC<SiglaProps> = ({ nome, curta, className }) => {
  // Sigla ausente do dicionário sai crua em vez de sair "undefined" na tela.
  // É defeito de programação, não do usuário, e ele não deve pagar por ele.
  if (!SIGLAS[nome]) return <>{nome}</>;
  if (curta) {
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
  }
  // `porExtenso` devolve "Programa de Gerenciamento de Riscos (PGR)"; aqui a
  // ordem é a inversa porque o texto ao redor já foi escrito com a sigla no
  // lugar do sujeito da frase — trocar a ordem obrigaria a reescrever cada
  // ocorrência nas telas.
  return (
    <span className={className}>
      {nome} <span className="opacity-90">({SIGLAS[nome].nome})</span>
    </span>
  );
};

/** A lista ao pé da tela, para quem chegou no meio do texto. */
export const GlossarioDeSiglas: React.FC<{
  termos: string[];
  className?: string;
}> = ({ termos, className }) => {
  const conhecidos = termos.filter((termo) => SIGLAS[termo]);
  if (!conhecidos.length) return null;
  return (
    <section
      className={
        className ??
        "mt-6 rounded-lg border border-slate-800 bg-slate-900/60 p-4"
      }
    >
      <p className="text-[11px] font-black uppercase tracking-wide text-slate-400">
        Siglas usadas nesta tela
      </p>
      <dl className="mt-2 space-y-1">
        {conhecidos.map((termo) => (
          <div key={termo} className="text-[11px] leading-4 text-slate-400">
            <dt className="inline font-black text-slate-300">{termo}</dt>
            <dd className="inline"> — {descricao(termo)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
};

export { porExtenso };
