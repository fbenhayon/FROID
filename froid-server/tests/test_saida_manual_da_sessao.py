"""Sempre existe uma saida manual.

Em 03/09/2026 uma sessao real foi perdida no meio: o microfone do profissional
parou de transmitir e, depois disso, nao houve como reconectar. Havia um
paciente do outro lado, esperando.

As duas falhas tinham a MESMA causa, e nenhuma delas era o microfone:

  1. `track.onended` no microfone do profissional chamava so `updateStatus`.
     O sistema anotava a queda e seguia. Nada readquiria a trilha.

  2. `startProfessionalRtcCall` nunca era chamado por acao humana — as duas
     unicas chamadas eram automaticas. Quando nenhuma heuristica disparava,
     nao restava nada para a pessoa fazer.

Somava-se a isso o freio de renegociacao, que limita a 4 tentativas e so se
zerava em `connected` ou apos 30s de silencio: se o lado do paciente gastasse
a cota e parasse de pedir, o silencio era permanente.

O padrao por tras dos tres: TOLERANTE A FALHAS VIROU SILENCIOSO. Cada caminho
de recuperacao estava correto e era automatico; nenhum tinha uma saida operada
por quem estava na frente da tela.

Este teste vigia a saida manual. Ela nao pode depender de heuristica nenhuma.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

PAINEL = SERVER_DIR.parent / "froid-dashboard" / "src"
SESSAO = (PAINEL / "pages" / "LiveSession.tsx").read_text(encoding="utf-8")
PACIENTE = (PAINEL / "pages" / "PatientSessionPage.tsx").read_text(encoding="utf-8")


class OhBotaoDeReligarEXISTE(unittest.TestCase):
    def test_ha_uma_funcao_de_religamento_completo(self):
        self.assertIn("const religarTudo = useCallback(", SESSAO)

    def test_ela_readquire_midia_e_nao_so_a_chamada(self):
        """Readquirir so a chamada nao resolveria a falha real: o microfone
        estava morto. `activateMedia` pega microfone e camera de novo e termina
        chamando `startProfessionalRtcCall` — um caminho para as duas falhas."""
        self.assertIn("await activateMediaRef.current?.()", SESSAO)
        self.assertIn("activateMediaRef.current = activateMedia", SESSAO)
        self.assertIn("void startProfessionalRtcCall(stream)", SESSAO)

    def test_o_botao_aparece_nos_TRES_layouts(self):
        """Quem escolhe layout simplificado nao escolheu ficar sem saida."""
        self.assertEqual(SESSAO.count("onClick={() => void religarTudo()}"), 3)
        self.assertEqual(SESSAO.count("Religar\n"), 3)

    def test_o_botao_nao_depende_de_condicao_para_aparecer(self):
        """Escondido atras de `rtcStatus === 'failed'` ele nao serviria: a
        falha de 03/09 nao se declarou como falha — a tela seguia parecendo
        viva. No dia em que o botao for necessario, ninguem vai procurar por
        ele num menu."""
        # A intencao esta escrita em cada um dos tres locais, e o botao nao
        # esta dentro de bloco condicional nenhum: os 24 caracteres antes de
        # cada `<button` sao o fim do comentario, nao um `&& (`.
        self.assertEqual(SESSAO.count("Fica sempre visivel de proposito"), 3)
        partes = SESSAO.split("onClick={() => void religarTudo()}")
        self.assertEqual(len(partes), 4)
        for antes in partes[:-1]:
            abertura = antes.rstrip().rsplit("{", 1)[-1]
            self.assertNotIn("&&", abertura)
            self.assertNotIn("?", abertura)


class OhMicrofoneQueCaiTENTAvoltar(unittest.TestCase):
    def test_onended_faz_mais_que_anotar(self):
        self.assertIn("void religarTudo(true)", SESSAO)

    def test_e_avisa_quem_esta_atendendo(self):
        self.assertIn("Microfone do profissional caiu", SESSAO)


class AsGuardasContraLoop(unittest.TestCase):
    """A recuperacao automatica nao pode virar o proximo defeito: um microfone
    USB intermitente encerraria a trilha, o religamento criaria outra, e a nova
    encerraria de novo."""

    def test_nao_ha_dois_getUserMedia_sobrepostos(self):
        self.assertIn("if (religandoRef.current) return;", SESSAO)

    def test_o_automatico_tem_limite_e_o_manual_nao(self):
        self.assertIn("if (automatico && religamentosAutomaticosRef.current >= 3)", SESSAO)
        self.assertIn("else religamentosAutomaticosRef.current = 0;", SESSAO)

    def test_o_limite_conta_quedas_em_SEQUENCIA(self):
        """Tres quedas em uma hora de consulta saudavel sao acidente, nao
        defeito de hardware. Sem a janela, a terceira seria recusada."""
        self.assertIn("ultimoReligamentoRef.current > 120_000", SESSAO)

    def test_o_limite_diz_o_que_fazer_em_vez_de_calar(self):
        self.assertIn("Verifique o cabo ou troque o dispositivo", SESSAO)


class OhFreioNaoPrendeAConexaoCAIDA(unittest.TestCase):
    """O freio existe para evitar livelock de renegociacao. Queda de conexao
    nao e livelock — e o momento em que mais se precisa de tentativas."""

    def test_o_freio_e_liberado_nas_duas_pontas(self):
        # Uma ponta so nao basta: se o lado do paciente gastar a cota e parar
        # de pedir, o lado do profissional espera um pedido que nao vem.
        self.assertGreaterEqual(SESSAO.count("freioRenegociacao.liberar()"), 3)
        self.assertGreaterEqual(PACIENTE.count("freioRenegociacao.liberar()"), 3)

    def test_o_motivo_esta_escrito_onde_alguem_vai_ler(self):
        self.assertIn("QUEDA DE CONEXAO NAO E LIVELOCK", SESSAO)


class ProcedenciaNaoSeChamaMaisSimulacao(unittest.TestCase):
    """`"mock"` prometia um gerador que nao existe mais. Onde nao houve medida
    o que existe e ausencia, e a tela tem de dizer isso — dizer "voz simulada"
    seria afirmar uma simulacao que nao aconteceu."""

    def test_a_tela_nao_escreve_voz_simulada(self):
        self.assertNotIn('"voz simulada"', SESSAO)
        self.assertIn('entry.source === "real_pcm" ? "voz medida" : "sem apuração"', SESSAO)

    def test_o_padrao_sem_declaracao_e_a_ausencia(self):
        self.assertIn('event.voice_features_source || "sem_apuracao"', SESSAO)


if __name__ == "__main__":
    unittest.main()
