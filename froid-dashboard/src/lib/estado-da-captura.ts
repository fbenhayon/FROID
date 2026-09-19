/**
 * Por que a voz não foi medida neste tique — e as duas respostas não são a
 * mesma.
 *
 * O motor publica `voice_features_source: "sem_apuracao"` em dois casos muito
 * diferentes, e até 19/09/2026 o painel tratava os dois como um só:
 *
 *   - o PCM do paciente não chegou. Falha de captura, perda irrecuperável, e o
 *     alarme vermelho está certo;
 *   - o PCM chegou e a janela não tinha voz vozeada. O paciente está calado
 *     enquanto o profissional fala — metade de qualquer consulta.
 *
 * Contados juntos, com o limiar de cinco tiques, o alarme "confira a permissão
 * de microfone" acendia a cada cinco segundos de silêncio e apagava na primeira
 * sílaba, sobre um microfone intacto. O profissional relatou o sintoma como o
 * que ele é: "fica entrando e saindo, parece instável".
 *
 * Isto vive fora de `LiveSession.tsx` porque é a regra que precisava de teste, e
 * uma regra dentro de um componente de sete mil linhas só se testa por `grep` no
 * fonte — que confirma que a linha existe, não que ela decide certo.
 */

export type EstadoDaCaptura =
  | "medida"
  | "sem_vozeamento"
  | "sem_audio"
  /** Motor anterior a 19/09/2026: não declara `estado_da_captura`. */
  | "desconhecido";

/** Tiques SEGUIDOS de cada situação. Zeram assim que ela deixa de valer. */
export interface TiquesDeCaptura {
  /** O áudio do paciente não está chegando ao motor. É falha. */
  semAudio: number;
  /** O áudio chega e não há voz vozeada. Não é falha. */
  emSilencio: number;
}

export const TIQUES_DE_CAPTURA_ZERADOS: TiquesDeCaptura = {
  semAudio: 0,
  emSilencio: 0,
};

/** Lê a procedência que o motor declara, sem adivinhar o que ele não disse.
 *
 *  Nada aqui infere estado a partir de prosa: `motivo_sem_apuracao` distingue os
 *  dois casos em português, e casar por pedaço de frase erra em silêncio no dia
 *  em que alguém reescrever a mensagem. */
export function classificarCaptura(meta: unknown): EstadoDaCaptura {
  if (!meta || typeof meta !== "object") return "desconhecido";
  const m = meta as Record<string, unknown>;
  const estado = m.estado_da_captura;
  if (estado === "medida" || estado === "sem_vozeamento" || estado === "sem_audio") {
    return estado;
  }
  // Motor antigo. Ele diz se houve voz medida, e não diz por que não houve.
  if (m.voice_features_source === "real_pcm") return "medida";
  return "desconhecido";
}

/** Atualiza as duas contagens com o tique que acabou de chegar.
 *
 *  `desconhecido` conta como falha DE PROPÓSITO: é o motor antigo, que não sabe
 *  separar os dois casos. Aviso a mais é ruído; aviso a menos foi a sessão de 18
 *  minutos analisada sem PCM nenhum, descoberta só no relatório, quando já não
 *  havia o que reprocessar. O painel desta casa sobe sem o backend com alguma
 *  frequência, então este ramo não é hipotético. */
export function contarCaptura(
  anterior: TiquesDeCaptura,
  meta: unknown,
): TiquesDeCaptura {
  const estado = classificarCaptura(meta);
  const falhou = estado === "sem_audio" || estado === "desconhecido";
  return {
    semAudio: falhou ? anterior.semAudio + 1 : 0,
    emSilencio: estado === "sem_vozeamento" ? anterior.emSilencio + 1 : 0,
  };
}
