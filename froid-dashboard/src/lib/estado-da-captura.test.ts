import { describe, expect, it } from "vitest";
import {
  classificarCaptura,
  contarCaptura,
  TIQUES_DE_CAPTURA_ZERADOS,
} from "./estado-da-captura";

/**
 * O alarme do microfone não pode acender sobre um microfone que funciona.
 *
 * Relato do profissional em 19/09/2026, durante um atendimento: "fica entrando
 * e saindo, parece instável". Na tela, duas frases ao mesmo tempo — a barra de
 * estado dizendo "Paciente conectado: áudio e vídeo recebidos · rota
 * srflx/srflx", e o alarme vermelho dizendo "Voz do paciente não está chegando
 * à análise. Confira a permissão de microfone na tela do paciente".
 *
 * As duas estavam sendo produzidas por caminhos diferentes, e a segunda estava
 * errada. O painel contava tique sem voz medida sem perguntar POR QUE não houve
 * voz, e o silêncio do paciente — que é metade de qualquer consulta — entrava na
 * mesma conta que a falha de captura. Cinco segundos de escuta e o alarme
 * acendia; a primeira sílaba e ele apagava.
 *
 * O dano não é o incômodo. É que a falha DE VERDADE, no dia em que o microfone
 * cair, vai parecer mais uma piscada das centenas daquela sessão — e o que não
 * for captado não se recupera depois.
 *
 * Os testes abaixo afirmam a garantia (o que o profissional precisa que seja
 * verdade na tela), não o mecanismo.
 */

const MEDIDA = { voice_features_source: "real_pcm", estado_da_captura: "medida" };
const CALADO = {
  voice_features_source: "sem_apuracao",
  estado_da_captura: "sem_vozeamento",
};
const SEM_AUDIO = {
  voice_features_source: "sem_apuracao",
  estado_da_captura: "sem_audio",
};

/** Roda uma sequência de tiques e devolve as contagens no fim. */
function sessao(tiques: unknown[]) {
  return tiques.reduce<ReturnType<typeof contarCaptura>>(
    (acc, meta) => contarCaptura(acc, meta),
    TIQUES_DE_CAPTURA_ZERADOS,
  );
}

function repetir(meta: unknown, vezes: number) {
  return Array.from({ length: vezes }, () => meta);
}

describe("silêncio do paciente não acende o alarme de captura", () => {
  it("dez minutos calado não contam um único tique de falha", () => {
    // Uma consulta em que o profissional fala e o paciente ouve. O microfone
    // está aberto o tempo todo.
    expect(sessao(repetir(CALADO, 600)).semAudio).toBe(0);
  });

  it("conta o silêncio, porém — ele não é falha, e também não é nada", () => {
    // Não alarmar é diferente de não saber. Se o paciente ESTIVER falando e o
    // motor não medir nada, é sinal fraco demais, e alguém tem de ficar
    // sabendo. O que muda é a cor e o texto, não a existência do aviso.
    expect(sessao(repetir(CALADO, 600)).emSilencio).toBe(600);
  });

  it("a conversa real não acumula falha: fala, pausa, fala", () => {
    const conversa = [
      ...repetir(MEDIDA, 8),
      ...repetir(CALADO, 40), // o profissional explicando
      ...repetir(MEDIDA, 12),
      ...repetir(CALADO, 25),
      ...repetir(MEDIDA, 5),
    ];
    expect(sessao(conversa).semAudio).toBe(0);
  });
});

describe("a falha de captura continua acendendo", () => {
  it("áudio que não chega conta como falha desde o primeiro tique", () => {
    expect(sessao(repetir(SEM_AUDIO, 5)).semAudio).toBe(5);
  });

  it("o motor que não sabe responder cai no lado que alarma", () => {
    // Motor anterior a 19/09/2026 não emite `estado_da_captura`. Sem ele não há
    // como separar falha de silêncio, e a saída honesta é a regra antiga: tudo
    // conta como falha. Aviso a mais é ruído; aviso a menos foi a sessão de 18
    // minutos analisada sem PCM nenhum, descoberta só no relatório.
    //
    // Não é hipotético: nesta casa o painel sobe com rebuild e o backend quase
    // nunca, então a versão nova do painel roda contra o motor antigo.
    const motorAntigo = { voice_features_source: "sem_apuracao" };
    expect(sessao(repetir(motorAntigo, 5)).semAudio).toBe(5);
  });

  it("payload sem audio_meta nenhum também alarma", () => {
    expect(sessao([undefined, null, {}]).semAudio).toBe(3);
  });

  it("a contagem zera quando a voz volta a ser medida", () => {
    // Senão o alarme ficaria aceso depois de resolvido, que é o defeito
    // simétrico: aviso que não some ensina a ignorar tão bem quanto aviso que
    // pisca.
    const contagem = sessao([...repetir(SEM_AUDIO, 30), MEDIDA]);
    expect(contagem.semAudio).toBe(0);
  });
});

describe("a leitura da procedência não adivinha o que o motor não disse", () => {
  it("lê o campo declarado, e não a prosa do motivo", () => {
    // `motivo_sem_apuracao` distingue os dois casos em português. Casar por
    // pedaço de frase erraria em silêncio no dia em que alguém reescrevesse a
    // mensagem — e apontar a causa errada é pior que não apontar nenhuma.
    const soProsa = {
      voice_features_source: "sem_apuracao",
      motivo_sem_apuracao: "janela sem voz vozeada: sinal presente, mas abaixo",
    };
    expect(classificarCaptura(soProsa)).toBe("desconhecido");
  });

  it("não confunde os três estados entre si", () => {
    expect(classificarCaptura(MEDIDA)).toBe("medida");
    expect(classificarCaptura(CALADO)).toBe("sem_vozeamento");
    expect(classificarCaptura(SEM_AUDIO)).toBe("sem_audio");
  });

  it("um valor que o painel não conhece não vira nenhum dos três", () => {
    const futuro = { estado_da_captura: "algo_que_ainda_nao_existe" };
    expect(classificarCaptura(futuro)).toBe("desconhecido");
    // E cai no lado que alarma, pela mesma razão de sempre.
    expect(sessao(repetir(futuro, 3)).semAudio).toBe(3);
  });
});
