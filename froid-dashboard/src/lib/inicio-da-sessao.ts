/**
 * Quando a sessão começou — e por que esperar não conta.
 *
 * Até 19/09/2026 os dois relógios do painel partiam do microfone DO
 * PROFISSIONAL: `elapsedSeconds`, pela condição `state.micOn` no `TICK`, e
 * `sessionStart`, escrito no `MEDIA_STATUS` no instante em que a trilha local
 * ficava viva. Nenhum dos dois tem relação com existir alguém do outro lado.
 *
 * O que isso produziu numa sessão real: o profissional abriu a tela, concedeu
 * a própria permissão, e o cronômetro começou a correr enquanto ele olhava
 * "Aguardando paciente...". Passados 2min30 sem conexão, ele encerrou.
 *
 * O dano vai além do cronômetro. `elapsedSeconds` é o eixo de tempo de tudo o
 * que se mede: carimba cada amostra, delimita cada corte, abre a janela de 60 s
 * da baseline e vira a duração impressa no relatório. E `sessionStart` alimenta
 * o encerramento automático aos 55 minutos — dez minutos de espera encurtavam
 * a consulta em dez.
 *
 * A regra mora aqui, e não dentro do componente de sete mil linhas, porque
 * dentro dele só se verifica por `grep` no fonte — que confirma que a linha
 * existe, nunca que ela decide certo.
 */

export interface SinaisDeInicio {
  /** Presencial PURO. O presencial-móvel não entra aqui: lá o paciente tem
   *  aparelho próprio e precisa conectar como no remoto. */
  presencial: boolean;
  /** Captura local do profissional. */
  micOn: boolean;
  cameraOn: boolean;
  /** Fluxo RTP de entrada medido, e não promessa de negociação. */
  remotePatientOn: boolean;
  remotePatientVideoOn: boolean;
}

/** A sessão existe? No remoto, só com o paciente do outro lado.
 *
 *  No presencial puro não há página do paciente, logo não há mídia dele para
 *  esperar: os dois estão na mesma sala e a captura local É a sessão. Exigir o
 *  paciente ali deixaria o relógio parado a consulta inteira — o defeito
 *  simétrico, e igualmente caro. */
export function sessaoComecou(sinais: SinaisDeInicio): boolean {
  if (sinais.presencial) return sinais.micOn || sinais.cameraOn;
  return sinais.remotePatientOn || sinais.remotePatientVideoOn;
}
