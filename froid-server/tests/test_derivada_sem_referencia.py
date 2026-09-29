"""Derivada sem janela anterior e ausencia declarada, nunca 0.0000.

O CASO, 22/09/2026
------------------
O Fabio abriu o painel e fotografou a faixa das derivadas cepstrais:

    DMFCC7 0.0000    DMFCC9 0.0000
    DDMFCC7 0.0000   DDMFCC9 0.0000

Os quatro campos cravados em zero, com a mesma tipografia de uma medida real
de zero. Havia DUAS pecas produzindo isso, uma de cada lado:

1. NO MOTOR. A falta de referencia era resolvida subtraindo o valor dele
   mesmo — `mfcc7 - (previous if previous is not None else mfcc7)` — que da
   exatamente 0.0. E `previous_delta_*` nascia 0.0, entao a segunda derivada
   saia 0.0 pelo mesmo caminho. Isso publicava "a voz nao variou" onde o
   correto era "nao houve como medir variacao". Regra 1.1 da casa.

2. NO PAINEL. `SpectralBandsChart` lia os quatro campos por um helper que
   devolve 0 para o que nao veio, e imprimia `.toFixed(4)`. Mesmo com o motor
   declarando null, a tela continuaria escrevendo 0.0000.

E HAVIA UMA GUARDA QUE NAO GUARDAVA
-----------------------------------
Derivada so faz sentido entre janelas da MESMA fonte: MFCC medido do PCM nao
se compara com o proxy espectral. Existia um bloco para zerar a referencia na
troca de ramo, com comentario explicando o pico falso que ele evitava — e ele
rodava DEPOIS do calculo, sendo as quatro atribuicoes sobrescritas duas linhas
abaixo pelo armazenamento do tick. Codigo morto descrevendo uma protecao que
nunca aconteceu; o tick da troca seguia publicando a diferenca entre grandezas
que nao se comparam. Movido para antes do calculo.

O QUE ESTE TESTE AFIRMA
-----------------------
A garantia, nos pontos onde ela pode quebrar — nao o mecanismo. Um tique sem
referencia comparavel declara ausencia; com referencia, publica a diferenca
medida; e o alerta espastico nao afirma nem nega sem aceleracao apurada.
"""
import time
import unittest

from froid_core import SessionState


def _tique(state: SessionState, mfcc=None):
    """Um tique com espectro. `mfcc` presente => ramo real; ausente => proxy."""
    features = {
        "voice_spectral_12": [5.0] * 12,
        "f0_mean": 150.0,
        "f0_voiced_ratio": 0.9,
        "zcr": 0.1,
    }
    if mfcc is not None:
        features["mfcc7"], features["mfcc9"] = mfcc
    state.pcm_received_at = time.time()
    state.pcm_revision += 1
    state.update_voice_features(features)
    return state.process_tick().get("audio_meta") or {}


DERIVADAS = ("mfcc7_delta", "mfcc9_delta", "mfcc7_delta_delta", "mfcc9_delta_delta")


class DerivadaSemReferencia(unittest.TestCase):
    def test_o_primeiro_tique_nao_publica_zero(self):
        estado = SessionState(session_id="t")
        audio = _tique(estado, (3.0, 4.0))
        for campo in DERIVADAS:
            self.assertIsNone(
                audio.get(campo),
                "%s saiu como %r no primeiro tique. Sem janela anterior a "
                "derivada nao existe, e 0.0 e indistinguivel de uma medida "
                "real de zero." % (campo, audio.get(campo)),
            )

    def test_com_referencia_a_derivada_e_a_diferenca_medida(self):
        estado = SessionState(session_id="t")
        _tique(estado, (3.0, 4.0))
        segundo = _tique(estado, (3.5, 4.2))
        self.assertAlmostEqual(segundo["mfcc7_delta"], 0.5, places=4)
        self.assertAlmostEqual(segundo["mfcc9_delta"], 0.2, places=4)
        # A SEGUNDA derivada ainda nao: ela precisa de duas derivadas, e so
        # existe uma. Declarar ausencia aqui tambem e o ponto.
        self.assertIsNone(segundo["mfcc7_delta_delta"])
        terceiro = _tique(estado, (3.9, 4.9))
        self.assertAlmostEqual(terceiro["mfcc7_delta"], 0.4, places=4)
        self.assertAlmostEqual(terceiro["mfcc7_delta_delta"], -0.1, places=4)

    def test_a_troca_de_ramo_mata_a_referencia_ANTES_do_calculo(self):
        """A guarda que existia e nao guardava. Ver o cabecalho deste arquivo."""
        estado = SessionState(session_id="t")
        _tique(estado, (3.0, 4.0))
        _tique(estado, (3.5, 4.2))
        proxy = _tique(estado, None)
        for campo in DERIVADAS:
            self.assertIsNone(
                proxy.get(campo),
                "%s saiu como %r no tique da troca real->proxy. MFCC medido do "
                "PCM nao se subtrai de proxy espectral: o pico dessa conta "
                "alimentava o alerta de contracao espastica." % (campo, proxy.get(campo)),
            )

    def test_sem_aceleracao_apurada_o_alerta_espastico_nao_afirma_nada(self):
        estado = SessionState(session_id="t")
        audio = _tique(estado, (3.0, 4.0))
        self.assertIsNone(audio["mfcc9_delta_delta"])
        self.assertIsNone(
            audio.get("mfcc9_delta_delta_spastic_alert"),
            "False diria 'conferi e nao ha contracao espastica', que e outra "
            "afirmacao — e sem aceleracao apurada ela e falsa.",
        )

    def test_o_painel_imprime_a_ausencia_em_vez_de_converter_para_zero(self):
        """O outro lado do mesmo defeito, travado no fonte do painel.

        Sem isto, o motor passa a declarar null e a tela segue escrevendo
        0.0000 — que foi exatamente o estado fotografado em 22/09/2026.
        """
        from pathlib import Path

        fonte = (
            Path(__file__).resolve().parents[2]
            / "froid-dashboard" / "src" / "components" / "indicators"
            / "SpectralBandsChart.tsx"
        ).read_text(encoding="utf-8")
        for rotulo in ("DMFCC7", "DMFCC9", "DDMFCC7", "DDMFCC9"):
            self.assertNotIn(
                "%s {mfcc" % rotulo, fonte.replace("{derivada(", "{DERIVADA("),
                "%s voltou a ser impresso direto do numero; use o formatador "
                "que imprime a ausencia." % rotulo,
            )
        self.assertIn("sem apuração", fonte)


if __name__ == "__main__":
    unittest.main()
