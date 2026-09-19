"""Silencio do paciente NAO e falha de captura, e o motor tem de dizer qual e qual.

Apurado em 19/09/2026, numa sessao real. O profissional via o alarme vermelho
"Voz do paciente nao esta chegando a analise — confira a permissao de microfone"
acender e apagar a sessao inteira, sobre um microfone que funcionava, enquanto a
barra de estado da chamada dizia, corretamente, "audio e video recebidos". Duas
frases na mesma tela, uma contradizendo a outra.

O painel contava os tiques sem voz medida e nao separava os dois motivos pelos
quais um tique sai sem voz:

  - o PCM nao chegou ao motor. Falha. Cada segundo assim e perda irrecuperavel,
    e o alarme vermelho esta certo;
  - o PCM chegou e a janela nao tinha voz vozeada. O paciente ouvindo enquanto o
    profissional fala — metade de qualquer consulta.

Com o limiar de cinco tiques, o segundo caso acendia o alarme a cada cinco
segundos de silencio e o apagava na primeira silaba. Alarme que pisca deixa de
ser lido, e o dia em que o microfone cair de verdade ele vai parecer mais uma
piscada. E o texto acusava o microfone do paciente, que estava intacto.

O motor SEMPRE soube a diferenca: ela viajava na prosa de `motivo_sem_apuracao`,
que nenhuma tela lia. O padrao desta casa — a peca existe, esta correta, e nada a
consome. Casar por pedaco de frase em portugues seria trocar um defeito por
outro; `estado_da_captura` e o campo que se pode LER.
"""
import math
import unittest

import numpy as np

import froid_voice
from froid_core import SessionState
from froid_f0 import pcm16_bytes_to_float


SR = 16000


def voz_vozeada(f0: float = 150.0, segundos: float = 3.0) -> bytes:
    """Pulso glotal — periodico, logo vozeado."""
    t = np.arange(int(SR * segundos)) / SR
    sig = sum((1.0 / k) * np.sin(2 * math.pi * f0 * k * t) for k in range(1, 13))
    sig = sig / np.max(np.abs(sig))
    return (sig * 30000).astype("<i2").tobytes()


def ruido_de_sala(segundos: float = 3.0) -> bytes:
    """Sinal presente e aperiodico: ha o que analisar, e nao ha voz.

    E o microfone aberto numa sala em que o paciente nao esta falando. O
    espectro sai completo; o vozeamento, nao.
    """
    rng = np.random.default_rng(20260919)
    sig = rng.normal(0.0, 1.0, int(SR * segundos))
    sig = sig / np.max(np.abs(sig))
    return (sig * 900).astype("<i2").tobytes()


def _com_pcm(state: SessionState, pcm: bytes) -> dict:
    buffer = state.ingest_pcm(pcm16_bytes_to_float(pcm), SR)
    state.update_voice_features(froid_voice.extract_voice_features(buffer, SR))
    return state.process_tick()


class EstadoDaCapturaTests(unittest.TestCase):
    def test_pcm_ausente_e_declarado_como_falha(self):
        """Nada chegou: e o unico caso que justifica falar de microfone."""
        payload = SessionState(session_id="s").process_tick()
        audio = payload["audio_meta"]
        self.assertEqual(audio["estado_da_captura"], "sem_audio")
        self.assertEqual(audio["voice_features_source"], "sem_apuracao")
        self.assertIn("nao chegou", payload["motivo_sem_apuracao"])

    def test_sinal_sem_vozeamento_NAO_e_declarado_como_falha(self):
        """O caso que acendia o alarme errado.

        Sem `estado_da_captura`, este tick e indistinguivel do de cima para
        quem le `voice_features_source` — e era exatamente assim que o painel
        lia. Os dois continuam `sem_apuracao`, porque nao houve voz medida, e
        isso esta certo: o que muda e o MOTIVO.
        """
        payload = _com_pcm(SessionState(session_id="s"), ruido_de_sala())
        audio = payload["audio_meta"]
        self.assertEqual(audio["voice_features_source"], "sem_apuracao")
        self.assertEqual(audio["estado_da_captura"], "sem_vozeamento")
        self.assertNotEqual(audio["estado_da_captura"], "sem_audio")
        # E a prosa continua dizendo a mesma coisa que o campo. Se as duas
        # divergirem, uma das telas vai mentir.
        self.assertIn("sem voz vozeada", payload["motivo_sem_apuracao"])

    def test_voz_medida_declara_medida(self):
        payload = _com_pcm(SessionState(session_id="s"), voz_vozeada())
        audio = payload["audio_meta"]
        self.assertEqual(audio["voice_features_source"], "real_pcm")
        self.assertEqual(audio["estado_da_captura"], "medida")

    def test_a_chave_existe_nos_TRES_casos(self):
        """Quem le `estado_da_captura` nao pode quebrar num dos ramos.

        A mesma garantia que o docstring de `_payload_sem_apuracao` ja exige do
        resto do dicionario, e que ja quebrou quatro testes de integracao uma
        vez: o conjunto de chaves e o MESMO, com ou sem apuracao. Um `KeyError`
        aqui derruba a tela no meio de um atendimento.
        """
        casos = {
            "sem_audio": SessionState(session_id="a").process_tick(),
            "sem_vozeamento": _com_pcm(SessionState(session_id="b"), ruido_de_sala()),
            "medida": _com_pcm(SessionState(session_id="c"), voz_vozeada()),
        }
        for esperado, payload in casos.items():
            with self.subTest(caso=esperado):
                self.assertEqual(payload["audio_meta"]["estado_da_captura"], esperado)

    def test_o_default_do_payload_sem_apuracao_alarma(self):
        """Falhar fechado vale para diagnostico tambem.

        Um chamador novo que esqueca `audio_chegou` faz o painel alarmar, e nao
        emudecer. Aviso a mais e ruido; aviso a menos e a sessao de 18 minutos
        perdida que originou este aviso.
        """
        state = SessionState(session_id="s")
        audio = state._payload_sem_apuracao("motivo qualquer")["audio_meta"]
        self.assertEqual(audio["estado_da_captura"], "sem_audio")


if __name__ == "__main__":
    unittest.main()
