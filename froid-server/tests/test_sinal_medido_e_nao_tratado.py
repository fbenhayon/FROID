"""O audio que a chamada usa nao serve para medir, e o que mede nao vai a tela sem procedencia.

Dois defeitos de 02/09/2026, achados na auditoria campo a campo.

PRIMEIRO — o microfone da analise era o da conversa.

A chamada abre o microfone com echoCancellation, noiseSuppression e
autoGainControl ligados, e faz certo: numa conversa voce quer os tres. Mas o
MESMO stream alimentava a analise acustica, e cada um destroi uma medida:

  autoGainControl   normaliza o ganho continuamente. `loudness_dbfs` e `rms`
                    passam a medir o AGC — e SHIMMER e perturbacao de
                    amplitude, exatamente o que o AGC suaviza.
  noiseSuppression  subtracao espectral: altera voice_spectral_12 (as 12
                    Zonas), MFCC7/9, ZCR, sub-harmonicos e todas as bandas.
  echoCancellation  processa o sinal outra vez.

Sobrava so a F0 relativamente intacta, porque YIN mede periodicidade e ela
resiste a ganho. O cabecalho de froid-acoustic.ts sempre afirmou capturar "PCM
cru, a rota mais correta cientificamente". A intencao estava certa; a
captacao, nao.

SEGUNDO — a prosa clinica saia sem consultar a procedencia.

`dissonanceTechnicalFactors` transformava os indices acusticos em frases
afirmativas. A pior: "pico persistente compativel com contracao espastica
involuntaria das cordas vocais por ativacao simpatica". Sem audio real, o
motor calcula esses indices sobre um espectro GERADO, e essa bandeira dispara
em cerca de um quarto dos ticks.

O motor SEMPRE declarou a origem em `voice_features_source`. Nenhuma tela
consultava.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

PAINEL_DIR = SERVER_DIR.parent / "froid-dashboard" / "src"
PACIENTE = (PAINEL_DIR / "pages" / "PatientSessionPage.tsx").read_text(encoding="utf-8")
PROFISSIONAL = (PAINEL_DIR / "pages" / "LiveSession.tsx").read_text(encoding="utf-8")
CORE = (SERVER_DIR / "froid_core.py").read_text(encoding="utf-8")


class AAnaliseUsaMicrofoneCru(unittest.TestCase):
    def test_pede_os_tres_processamentos_desligados(self):
        self.assertIn("echoCancellation: false", PACIENTE)
        self.assertIn("noiseSuppression: false", PACIENTE)
        self.assertIn("autoGainControl: false", PACIENTE)

    def test_a_chamada_continua_com_processamento(self):
        """Desligar na chamada seria trocar um defeito por outro: sem
        cancelamento de eco, a sessao vira um problema para os dois lados."""
        self.assertIn("echoCancellation: true", PACIENTE)
        self.assertIn("noiseSuppression: true", PACIENTE)
        self.assertIn("autoGainControl: true", PACIENTE)

    def test_pedir_nao_e_obter_e_o_codigo_confere(self):
        """Alguns dispositivos ignoram as constraints e devolvem a trilha ja
        aberta. `getSettings` diz o que de fato valeu."""
        self.assertIn("getSettings?.()", PACIENTE)
        self.assertIn("ajustes.autoGainControl === false", PACIENTE)

    def test_a_captura_usa_o_stream_de_analise(self):
        self.assertIn("startF0Capture(streamDeAnalise || stream", PACIENTE)

    def test_quando_nao_e_cru_isso_e_DECLARADO(self):
        # Degradar em silencio foi o defeito da manha; repeti-lo aqui seria
        # trocar um microfone errado por um microfone errado e mudo.
        self.assertIn("microfone PROCESSADO", PACIENTE)
        self.assertIn("microfone CRU", PACIENTE)

    def test_a_trilha_crua_e_fechada_em_TODO_caminho_de_saida(self):
        """E um SEGUNDO microfone aberto. Sair da sessao sem fecha-lo deixa a
        luz do microfone acesa depois que a consulta acabou."""
        self.assertGreaterEqual(
            PACIENTE.count("analiseStreamRef.current?.getTracks().forEach((t) => t.stop())"),
            3,
        )


class ProsaClinicaExigeMedida(unittest.TestCase):
    def test_os_fatores_tecnicos_consultam_a_procedencia(self):
        i = PROFISSIONAL.index("function dissonanceTechnicalFactors")
        trecho = PROFISSIONAL[i : i + 1800]
        self.assertIn('audioMeta?.voice_features_source === "real_pcm"', trecho)

    def test_sem_medida_o_profissional_le_que_nao_ha_medida(self):
        self.assertIn("Sem áudio medido do paciente nesta janela", PROFISSIONAL)

    def test_a_frase_espastica_continua_existindo_para_o_caso_medido(self):
        """O portao nao pode virar censura: com voz real, o achado vale e deve
        aparecer."""
        self.assertIn("contração espástica involuntária", PROFISSIONAL)


class OMotorContinuaDeclarandoAOrigem(unittest.TestCase):
    """O portao so funciona porque o motor diz a verdade. Se estes campos
    sairem, as telas voltam a nao ter como perguntar."""

    def test_origem_da_voz(self):
        self.assertIn('"voice_features_source": "real_pcm" if', CORE)

    def test_origem_da_face(self):
        self.assertIn('"facs_source": facs_source', CORE)


class TresDefeitosInequivocos(unittest.TestCase):
    """Achados da auditoria que nao dependem de decisao clinica para corrigir."""

    def test_zero_dBFS_nao_vira_silencio(self):
        """`x or -120.0` e armadilha: em Python `0.0 or -120.0` da -120.0.

        E 0 dBFS e o sinal MAIS ALTO possivel — fundo de escala. A guarda
        transformava o extremo superior no extremo inferior, justamente no pico
        que mais interessa clinicamente.
        """
        self.assertNotIn('real.get("loudness_dbfs") or -120.0', CORE)
        self.assertIn("if _loud is not None else -120.0", CORE)

    def test_derivada_nao_cruza_ramos(self):
        """Delta so tem sentido entre janelas da MESMA fonte.

        `previous_*` era atualizado sempre, entao o primeiro tick com voz real
        subtraia MFCC medido de um proxy espectral gerado — e o pico resultante
        alimentava o alerta de contracao espastica.
        """
        self.assertIn("previous_mfcc_source", CORE)
        self.assertIn('_ramo = "real" if (real and "mfcc7" in real) else "proxy"', CORE)
        self.assertIn("if _ramo != self.previous_mfcc_source:", CORE)

    def test_o_campo_de_ramo_e_declarado_no_dataclass(self):
        """Atribuir atributo inexistente num dataclass sem slots CRIA o atributo
        em silencio — o reset viraria no-op e ninguem perceberia."""
        import dataclasses

        import froid_core

        campos = {f.name for f in dataclasses.fields(froid_core.SessionState)}
        self.assertIn("previous_mfcc_source", campos)
        self.assertIn("previous_delta_mfcc7", campos)

    def test_o_nome_deixou_de_mentir(self):
        """A variavel dizia ZCR e a formula usa JITTER. Renomear nao muda valor;
        trocar a formula mudaria a escala de dna_dissociative_shutdown, e essa e
        decisao clinica."""
        self.assertNotIn("zcr_drop_ratio", CORE)
        self.assertIn("estabilidade_de_jitter", CORE)


if __name__ == "__main__":
    unittest.main()
