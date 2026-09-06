// As duas contas que decidiam se um corte publica medida ou ausência.
//
// Viviam dentro de `LiveSession.tsx`, um módulo React de sete mil linhas que
// nenhum teste consegue importar — então eram verificadas por leitura do texto
// do arquivo, quando eram verificadas. As duas falharam em produção na sessão
// froid-mtpuwdafchqj, em 06/09/2026, e nenhum teste caiu.
//
// Aqui elas são funções puras, e o teste exercita o comportamento.

export type SegmentoTranscrito = { elapsedSeconds: number; text: string };

/** O prefixo que `speakerPrefix` escreve na frente de cada linha do paciente.
 *
 *  `PAC - ` é aceito por compatibilidade: sessões antigas gravaram esse
 *  prefixo, e ignorá-lo faria a fala do paciente sumir da contagem — o mesmo
 *  erro com o sinal trocado. */
const PREFIXO_DO_PACIENTE = /^\s*(PC|PAC)\s*-\s*/i;

/** Só o que o PACIENTE disse na janela, já sem o prefixo do falante.
 *
 *  AS DUAS BANDAS SÃO INDEPENDENTES, E ESTAVAM CERTAS. Numa sessão remota há
 *  dois pipelines de transcrição separados, cada um com o falante fixo em
 *  constante: `startSpeechToText(patientTranscriptStream, "PC", "patient")` na
 *  trilha WebRTC do paciente e `startSpeechToText(stream, "DR",
 *  "professional")` no microfone local. `appendTranscriptText` tem um único
 *  chamador, e ele sempre passa esse rótulo como override — a identificação
 *  por voz (`attributedSpeakerRef`) só decide no modo presencial, em que
 *  existe uma banda só para a sala inteira. Áudio nenhum foi misturado.
 *
 *  O defeito era do CONSUMIDOR. As linhas entram na mesma lista, corretamente
 *  marcadas, e quem contava palavras apagava os dois prefixos com um regex e
 *  somava tudo. A separação existia ponta a ponta; uma métrica a jogou fora.
 *
 *  Foi assim que a sessão froid-mtpuwdafchqj publicou 92,4; 135,7; 134,9 e
 *  113,8 palavras/min num relatório cujo próprio aviso dizia que nenhuma das
 *  1077 amostras recebeu voz real do paciente. Os números não eram inventados,
 *  e não vieram de trilha trocada: eram a fala do profissional, contada como
 *  se fosse a do paciente porque o rótulo foi descartado na leitura.
 *
 *  Aqui a linha do profissional é DESCARTADA, não desmarcada. */
export function transcricaoDoPaciente(
  segmentos: SegmentoTranscrito[],
  segundoInicial: number,
  segundoFinal: number,
): string {
  return (Array.isArray(segmentos) ? segmentos : [])
    .filter(
      (segmento) =>
        segmento &&
        segmento.elapsedSeconds >= segundoInicial &&
        segmento.elapsedSeconds < segundoFinal,
    )
    .map((segmento) => String(segmento.text || ""))
    .filter((texto) => PREFIXO_DO_PACIENTE.test(texto))
    .map((texto) => texto.replace(PREFIXO_DO_PACIENTE, ""))
    .join(" ")
    .trim();
}

/** Palavras por minuto do PACIENTE na janela — nula sem fala dele transcrita.
 *
 *  Zero seria uma afirmação: "o paciente falou a zero palavras por minuto". E
 *  não há como distinguir paciente calado de captura que não rodou. Sem
 *  nenhuma linha do PC o que existe é ausência de apuração, e ela se declara.
 *  Havendo linha, a contagem é medida e vale inclusive quando é baixa. */
export function palavrasPorMinutoDoPaciente(
  segmentos: SegmentoTranscrito[],
  segundoInicial: number,
  segundoFinal: number,
): number | null {
  const texto = transcricaoDoPaciente(segmentos, segundoInicial, segundoFinal);
  if (!texto) return null;
  const palavras = texto.split(/\s+/).filter(Boolean).length;
  const minutos = Math.max(1 / 60, (segundoFinal - segundoInicial) / 60);
  return Math.round((palavras / minutos) * 10) / 10;
}

/** Diferença entre duas medidas — NULA se qualquer uma não foi apurada.
 *
 *  `a - b` em JavaScript trata `null` como zero, então um corte sem apuração
 *  contra uma baseline de IPM 47 produzia `-47`: uma queda dramática que
 *  ninguém mediu, publicada como delta no relatório e no acervo do Data-Froid.
 *  Ausência menos medida é ausência, não variação. */
export function menos(
  a: number | null | undefined,
  b: number | null | undefined,
): number | null {
  if (typeof a !== "number" || !Number.isFinite(a)) return null;
  if (typeof b !== "number" || !Number.isFinite(b)) return null;
  return a - b;
}
