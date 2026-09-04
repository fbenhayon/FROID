// O botão de corte, onde a mão já está.
//
// Fechar um corte sempre foi possível — o controle existia dentro do painel de
// resumo, que fica noutra coluna. Durante o atendimento o profissional olha
// para o rosto do paciente, não para a coluna lateral: procurar o botão custa
// exatamente o momento que se quis marcar.
//
// Por isso ele se sobrepõe ao vídeo, embaixo à esquerda: fora do rosto (que
// ocupa o centro) e fora da faixa de status (que ocupa o alto à esquerda).
//
// Um centímetro é medida de dedo, não de tela — por isso `1cm` literal em vez
// de pixel. Em telas de densidade diferente o CSS resolve para o mesmo tamanho
// físico aproximado, que é o que importa num alvo para clicar sem olhar.

import React from "react";

type Props = {
  onClick: () => void;
  /** Verdadeiro nos 10 primeiros segundos do corte e enquanto um fecha. */
  disabled?: boolean;
  /** O atalho, escrito na dica — atalho que ninguém descobre não existe. */
  atalho?: string;
};

export const BotaoDeCorte: React.FC<Props> = ({
  onClick,
  disabled = false,
  atalho = "Ctrl + Espaço",
}) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    title={
      disabled
        ? "Corte indisponível — aguarde 10 segundos desde o corte anterior"
        : `Fechar o corte agora (${atalho})`
    }
    aria-label="Fechar o corte agora"
    aria-keyshortcuts="Control+Space"
    className={`absolute bottom-3 left-3 z-30 flex h-[1cm] w-[1cm] items-center justify-center rounded-full border-2 text-[8px] font-black uppercase leading-none tracking-tight shadow-lg transition ${
      disabled
        ? "cursor-not-allowed border-amber-900 bg-amber-950/70 text-amber-700"
        : "border-amber-400 bg-amber-500 text-amber-950 hover:bg-amber-400 active:scale-95"
    }`}
  >
    Corte
  </button>
);
