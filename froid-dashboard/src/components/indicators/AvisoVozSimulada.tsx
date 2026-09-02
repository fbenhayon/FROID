// O aviso que faltava quando o motor analisa voz SIMULADA.
//
// O que aconteceu em 02/09/2026: uma sessão real de 24 minutos rodou inteira
// com o motor em modo simulado. F0 média 0.00, ZCR 0.000, derivadas cepstrais
// zeradas — e o painel exibindo IPM, MFCC e índices DNA com a mesma aparência
// de sempre. O Fábio percebeu porque vários índices não variavam; nada na tela
// dizia por quê.
//
// A causa está em `froid-acoustic.ts` e no portão que a chamava. A consequência
// é o que este componente trata: sem aviso, um relatório construído sobre dados
// simulados é indistinguível de um relatório clínico legítimo. Isso não é um
// detalhe de interface — é a diferença entre um documento que pode ser lido e
// um que não pode.
//
// O aviso nomeia o estado, diz o que ainda vale, e diz o que fazer.

import React from "react";

type Props = {
  /** `voice_features_source` do motor: "real_pcm" quando há voz de verdade. */
  origem?: string;
  /** O que o navegador do paciente relatou, quando relatou. */
  motivo?: string;
};

const EXPLICACAO: Record<string, string> = {
  "sem-audio": "O navegador do paciente não encontrou trilha de microfone.",
  "sem-suporte":
    "O navegador do paciente não suporta AudioWorklet — a análise acústica não roda nele.",
  "aguardando-gesto":
    "O navegador do paciente suspendeu o áudio até um toque na tela. Peça a ele que clique em qualquer ponto da página.",
  "sessao-inativa":
    "O áudio está subindo, mas a análise deste painel ainda não estava aberta quando ele começou.",
  erro: "A captura de áudio do paciente falhou ao iniciar.",
};

export const AvisoVozSimulada: React.FC<Props> = ({ origem, motivo }) => {
  // Enquanto a origem não chega, não há o que afirmar — e afirmar cedo demais
  // faria o aviso piscar no início de toda sessão saudável.
  if (!origem || origem === "real_pcm") return null;

  const explicacao = motivo ? EXPLICACAO[motivo] : "";

  return (
    <div className="shrink-0 rounded-lg border border-amber-600 bg-amber-950/50 px-2.5 py-2">
      <p className="text-[9px] font-black uppercase tracking-wider text-amber-400">
        Voz simulada — não use para leitura clínica
      </p>
      <p className="mt-1 text-[10px] leading-4 text-amber-100/90">
        O áudio real do paciente não chegou ao motor. Os índices acústicos
        exibidos abaixo são <strong>gerados</strong>, não medidos.
      </p>
      {explicacao && (
        <p className="mt-1 border-t border-amber-800/60 pt-1 text-[10px] leading-4 text-amber-100/75">
          {explicacao}
        </p>
      )}
      <p className="mt-1 text-[9px] leading-4 text-amber-100/60">
        A transcrição, o vídeo e o registro da sessão continuam válidos. O que
        não vale são F0, ZCR, MFCC e os índices derivados deles.
      </p>
    </div>
  );
};
