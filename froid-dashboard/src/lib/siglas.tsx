// Nenhuma sigla chega ao cliente sozinha.
//
// O leitor destas telas é o empresário e o técnico de segurança do trabalho da
// empresa contratante, não quem escreveu a norma. "O período do PGR a que esta
// avaliação se refere" é uma frase que só informa quem já sabe o que é PGR — e
// para quem não sabe ela não é neutra, é intimidante: a pessoa está prestes a
// assinar um serviço cujo vocabulário não domina.
//
// A regra desta base de código passa a ser: sigla visível ao usuário sai por
// <Sigla>, nunca digitada solta no texto. Isso garante que a denominação
// completa exista em UM lugar (se o nome oficial mudar, muda aqui) e que
// nenhuma tela invente uma expansão diferente da vizinha.
//
// Três formas de apresentação, e cada uma resolve um problema diferente:
//
//   <Sigla nome="PGR" />          PGR (Programa de Gerenciamento de Riscos)
//   <Sigla nome="PGR" curta />    PGR — com a denominação no title, para as
//                                 repetições dentro do mesmo parágrafo, onde
//                                 expandir de novo faria o texto ilegível
//   <GlossarioDeSiglas termos={[...]} />  a lista ao pé da tela
//
// O glossário existe porque `title` é hover, e hover não existe em telefone.
// Ele é a garantia de que a denominação completa está VISÍVEL na tela, e não a
// um gesto de distância que metade dos leitores não tem.

import React from "react";

export const SIGLAS: Record<string, string> = {
  "NR-1": "Norma Regulamentadora nº 1 — Disposições Gerais e Gerenciamento de Riscos Ocupacionais",
  "NR-17": "Norma Regulamentadora nº 17 — Ergonomia",
  PGR: "Programa de Gerenciamento de Riscos",
  GRO: "Gerenciamento de Riscos Ocupacionais",
  AEP: "Avaliação Ergonômica Preliminar",
  AET: "Análise Ergonômica do Trabalho",
  PCMSO: "Programa de Controle Médico de Saúde Ocupacional",
  CIPA: "Comissão Interna de Prevenção de Acidentes e de Assédio",
  SST: "Segurança e Saúde no Trabalho",
  MTE: "Ministério do Trabalho e Emprego",
  LGPD: "Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018)",
  CNPJ: "Cadastro Nacional da Pessoa Jurídica",
  CPF: "Cadastro de Pessoas Físicas",
  "ME/EPP": "Microempresa e Empresa de Pequeno Porte",
  eSocial:
    "Sistema de Escrituração Digital das Obrigações Fiscais, Previdenciárias e Trabalhistas",
  CAT: "Comunicação de Acidente de Trabalho",
  ISO: "Organização Internacional de Normalização",
  CFP: "Conselho Federal de Psicologia",
  MPT: "Ministério Público do Trabalho",
};

type SiglaProps = {
  nome: string;
  /** Repetição: mostra só a sigla, com a denominação no atributo `title`. */
  curta?: boolean;
  className?: string;
};

/** Uma sigla e o que ela quer dizer. */
export const Sigla: React.FC<SiglaProps> = ({ nome, curta, className }) => {
  const denominacao = SIGLAS[nome];
  // Sigla ausente do dicionário sai crua em vez de sair "undefined" na tela.
  // É defeito de programação, não do usuário, e ele não deve pagar por ele.
  if (!denominacao) return <>{nome}</>;
  if (curta) {
    return (
      <abbr
        title={denominacao}
        className={
          className ??
          "cursor-help underline decoration-dotted underline-offset-2"
        }
      >
        {nome}
      </abbr>
    );
  }
  return (
    <span className={className}>
      {nome} <span className="opacity-90">({denominacao})</span>
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
            <dd className="inline"> — {SIGLAS[termo]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
};
