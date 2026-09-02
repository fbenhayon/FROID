// O aviso que faltava quando o acesso trava por saldo.
//
// O que acontecia sem ele, e aconteceu com o Fábio em 02/09/2026:
//
// `onboarding_required` fica verdadeiro quando as sessões acabam. O roteador
// então manda a pessoa para onde ela resolveria isso — e para quem é
// administrador manda para /admin, por uma correção anterior que evitava outro
// círculo. Só que /admin não vende sessão. A pessoa cai numa tela que não tem
// relação com o problema, sem uma linha explicando o que houve, e qualquer
// tentativa de ir para o painel é devolvida para lá.
//
// Ele descobriu a causa lendo o código-fonte. Um profissional cliente não teria
// como — ligaria dizendo que o sistema quebrou, e estaria certo.
//
// O aviso nomeia a causa e oferece a saída. É o mínimo que uma tela deve a
// quem foi parado por ela.

import React from "react";
import { Link } from "react-router-dom";

type Props = {
  restam?: number;
  usadas?: number;
  total?: number;
  /** Cobranças pendentes bloqueiam o início de novas sessões. */
  pendencias?: number;
  /** O período de avaliação terminou. */
  avaliacaoEsgotada?: boolean;
  /** Administrador vê o caminho extra para o painel administrativo. */
  admin?: boolean;
};

export const AvisoSemSaldo: React.FC<Props> = ({
  restam = 0,
  usadas,
  total,
  pendencias = 0,
  avaliacaoEsgotada = false,
  admin = false,
}) => {
  // A causa muda a saída, então ela é dita antes — e é uma só, escolhida em
  // ordem de precedência. Listar três motivos possíveis deixaria a pessoa
  // adivinhando qual é o dela.
  const causa = pendencias > 0
    ? {
        titulo: "Há cobrança pendente de acerto",
        texto:
          `Existem ${pendencias} sessão(ões) realizadas com acerto pendente. ` +
          "O início de novas sessões fica bloqueado até a regularização — " +
          "as sessões já feitas continuam gravadas e acessíveis.",
        acao: "Regularizar",
      }
    : avaliacaoEsgotada
      ? {
          titulo: "O período de avaliação terminou",
          texto:
            "As sessões de avaliação foram utilizadas. Para continuar atendendo, " +
            "escolha um pacote.",
          acao: "Ver os pacotes",
        }
      : {
          titulo: "Suas sessões acabaram",
          texto:
            "O saldo chegou a zero, e por isso o sistema não abre uma sessão nova. " +
            "Nada foi perdido: pacientes, relatórios e histórico continuam no lugar.",
          acao: "Comprar sessões",
        };

  return (
    <section className="mx-auto mt-8 max-w-2xl rounded-lg border border-amber-700 bg-amber-950/40 p-6">
      <p className="text-[10px] font-black uppercase tracking-wide text-amber-400">
        Acesso interrompido
      </p>
      <h2 className="mt-1 text-lg font-black text-amber-100">{causa.titulo}</h2>
      <p className="mt-2 text-xs leading-5 text-amber-100/85">{causa.texto}</p>

      {(total !== undefined || usadas !== undefined) && (
        <div className="mt-4 flex flex-wrap gap-4 rounded border border-amber-800/60 bg-amber-950/40 px-4 py-3 text-[11px] text-amber-100/80">
          {total !== undefined && (
            <span>
              Contratadas <strong className="text-amber-100">{total}</strong>
            </span>
          )}
          {usadas !== undefined && (
            <span>
              Utilizadas <strong className="text-amber-100">{usadas}</strong>
            </span>
          )}
          <span>
            Disponíveis <strong className="text-amber-100">{restam}</strong>
          </span>
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        <Link
          to="/access/register"
          className="rounded-lg bg-amber-500 px-4 py-2 text-xs font-black text-amber-950 hover:bg-amber-400"
        >
          {causa.acao}
        </Link>
        {/* O administrador tinha o caminho para /admin e NENHUM de volta. */}
        {admin && (
          <Link
            to="/admin"
            className="rounded-lg border border-amber-700 px-4 py-2 text-xs font-black text-amber-100 hover:bg-amber-900/40"
          >
            Painel administrativo
          </Link>
        )}
        <a
          href="mailto:suporte@froid.com.br?subject=Acesso%20interrompido%20por%20saldo"
          className="rounded-lg border border-amber-700 px-4 py-2 text-xs font-black text-amber-100 hover:bg-amber-900/40"
        >
          Falar com o suporte
        </a>
      </div>

      <p className="mt-4 border-t border-amber-800/60 pt-3 text-[10px] leading-4 text-amber-100/60">
        O bloqueio vale para <strong>iniciar</strong> sessões novas. Relatórios já
        gravados, histórico de pacientes e documentos continuam acessíveis.
      </p>
    </section>
  );
};
