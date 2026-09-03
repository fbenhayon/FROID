// O que o profissional precisa saber ANTES de começar, para não interpretar
// mal o que vai ver.
//
// Por que existe: em 03/09/2026 três comportamentos do FROID mudaram de um jeito
// que, sem explicação, parecem defeito:
//
//   1. A linha de base só se constrói com voz medida do PACIENTE. Antes ela
//      travava em 60 ticks de qualquer jeito, inclusive sobre espectro gerado.
//      Agora, se o paciente ficar calado no primeiro minuto, ela simplesmente
//      não trava — e sem referência os desvios não valem.
//
//   2. Um aviso âmbar aparece sempre que não há voz para medir. Não é falha: é
//      o sistema dizendo que não apurou, em vez de calcular sobre silêncio.
//      Quem não souber disso vai ler como erro.
//
//   3. Em atendimento presencial com um microfone só, a separação entre as duas
//      falas depende da assinatura de voz do profissional estar cadastrada.
//      Sem ela, o microfone local é atribuído INTEIRO ao paciente.
//
// O terceiro item é o mais caro de descobrir depois: os primeiros minutos de
// consulta são tipicamente o profissional falando, e essa fala entraria nas
// métricas do paciente sem nada acusar.
//
// O aviso se fecha e é lembrado por sessão. Não é um alerta — é uma instrução
// de uso, e instrução repetida a cada tela vira ruído que se aprende a ignorar.

import React, { useState } from "react";

type Props = {
  /** `presential` exige assinatura de voz para separar os dois falantes. */
  modo?: string;
  /** O profissional já cadastrou a própria voz? Só importa no presencial. */
  vozDoProfissionalCadastrada?: boolean;
  /** Chave de persistência por sessão, para não repetir a cada render. */
  sessionId?: string;
};

const CHAVE = "froid_recomendacoes_vistas";

function jaViu(sessionId: string): boolean {
  try {
    return sessionStorage.getItem(`${CHAVE}:${sessionId}`) === "1";
  } catch {
    // Navegador com armazenamento bloqueado: mostrar de novo é melhor que
    // esconder uma instrução de uso.
    return false;
  }
}

export const RecomendacoesDeUso: React.FC<Props> = ({
  modo = "remote",
  vozDoProfissionalCadastrada = false,
  sessionId = "",
}) => {
  const [aberto, setAberto] = useState(() => !jaViu(sessionId));

  const presencialSemVoz = modo === "presential" && !vozDoProfissionalCadastrada;

  const fechar = () => {
    setAberto(false);
    try {
      sessionStorage.setItem(`${CHAVE}:${sessionId}`, "1");
    } catch {
      /* sem armazenamento, reaparece na próxima — aceitável */
    }
  };

  if (!aberto) {
    return (
      <button
        type="button"
        onClick={() => setAberto(true)}
        className="shrink-0 rounded border border-slate-700 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-slate-400 hover:bg-slate-800"
      >
        Recomendações de uso
      </button>
    );
  }

  return (
    <section className="shrink-0 rounded-lg border border-blue-700 bg-blue-950/40 px-3 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[10px] font-black uppercase tracking-wider text-blue-300">
          Recomendações de uso — leia antes de começar
        </p>
        <button
          type="button"
          onClick={fechar}
          className="shrink-0 rounded border border-blue-700 px-2 py-0.5 text-[9px] font-bold uppercase text-blue-200 hover:bg-blue-900/60"
        >
          Entendi
        </button>
      </div>

      <ol className="mt-2 space-y-2 text-[11px] leading-4 text-blue-100/90">
        <li>
          <strong className="text-blue-100">
            Deixe o paciente falar no primeiro minuto.
          </strong>{" "}
          A linha de base se constrói só com a voz dele, medida. Se esse minuto
          for a sua fala, a referência não trava — e sem referência os desvios
          da sessão não têm contra o que ser comparados.
        </li>
        <li>
          <strong className="text-blue-100">
            O aviso âmbar não é defeito.
          </strong>{" "}
          Ele aparece quando não há voz para medir — enquanto o paciente escuta,
          por exemplo. O sistema informa que não apurou em vez de calcular sobre
          silêncio. Índice em branco significa "não medido", nunca "zero".
        </li>
        {presencialSemVoz ? (
          <li className="rounded border border-amber-600 bg-amber-950/40 px-2 py-1.5">
            <strong className="text-amber-200">
              Atenção — presencial sem sua voz cadastrada.
            </strong>{" "}
            Com um microfone só para os dois, e sem a sua assinatura de voz, o
            áudio é atribuído <strong>inteiro ao paciente</strong> — inclusive a
            sua fala. Cadastre sua voz antes de começar, ou trate as métricas
            desta sessão como não separadas.
          </li>
        ) : (
          <li>
            <strong className="text-blue-100">As falas são separadas por canal.</strong>{" "}
            Cada microfone é transcrito no seu próprio canal: DR para você, PC
            para o paciente. A atribuição não é adivinhada pelo conteúdo.
          </li>
        )}
        <li>
          <strong className="text-blue-100">Fone de ouvido ajuda a medir.</strong>{" "}
          Sem ele, a voz do paciente sai pelo seu alto-falante e volta pelo seu
          microfone. O sistema tem guarda para isso, mas evitar é melhor que
          corrigir.
        </li>
      </ol>
    </section>
  );
};
