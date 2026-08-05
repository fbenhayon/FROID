"""O cadastro de operacoes precisa cobrir o que o sistema realmente faz."""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import lgpd_registry as R  # noqa: E402


class BaseLegalTests(unittest.TestCase):
    def test_nr1_nao_usa_consentimento(self):
        # O ponto central do parecer: consentimento na relacao de emprego e
        # viciado pela hierarquia, e a NR-1 ja obriga o levantamento.
        for op in R.OPERACOES:
            if op.chave.startswith("nr1_"):
                self.assertNotIn("consentimento", op.base_legal.lower(), op.chave)

    def test_resposta_do_colaborador_e_obrigacao_legal_para_dado_sensivel(self):
        op = next(o for o in R.OPERACOES if o.chave == "nr1_resposta_questionario")
        self.assertEqual(op.base_legal, R.OBRIGACAO_LEGAL_SENSIVEL)
        self.assertEqual(op.classe_dado, "sensivel")
        self.assertEqual(op.controlador, "Empresa empregadora")

    def test_estudo_de_validade_continua_com_consentimento(self):
        # A recomendacao de tirar consentimento vale para o fluxo NR-1. Aplicar
        # por analogia ao estudo quebraria a pesquisa: la e voluntaria,
        # separavel do atendimento, e quem consente e paciente e nao empregado.
        op = next(o for o in R.OPERACOES if o.chave == "estudo_validade")
        self.assertEqual(op.base_legal, R.CONSENTIMENTO_PESQUISA)

    def test_toda_operacao_tem_base_retencao_e_controlador(self):
        for op in R.OPERACOES:
            self.assertTrue(op.base_legal.strip(), op.chave)
            self.assertTrue(op.retencao.strip(), op.chave)
            self.assertTrue(op.controlador.strip(), op.chave)
            self.assertIn(op.classe_dado, ("comum", "sensivel", "anonimizado"))

    def test_toda_base_legal_cita_o_artigo(self):
        for op in R.OPERACOES:
            self.assertIn("art.", op.base_legal, op.chave)


class AvisoAoColaboradorTests(unittest.TestCase):
    def test_aviso_diz_que_informa_e_nao_consulta(self):
        texto = R.AVISO_BASE_LEGAL_NR1.lower()
        self.assertIn("informado, e não consultado", R.AVISO_BASE_LEGAL_NR1)
        self.assertIn("art. 11, ii", texto)
        self.assertIn("art. 7º, ii", texto)
        self.assertNotIn("aceito", texto)
        self.assertNotIn("autorizo", texto)

    def test_base_legal_e_anexada_ao_texto_da_empresa(self):
        composto = R.compose_purpose_notice("Aviso da empresa.")
        self.assertIn("Aviso da empresa.", composto)
        self.assertIn("art. 11, II", composto)

    def test_texto_vazio_ainda_produz_a_base_legal(self):
        self.assertIn("art. 11, II", R.compose_purpose_notice(""))

    def test_nao_duplica_quando_ja_presente(self):
        uma = R.compose_purpose_notice("Aviso.")
        duas = R.compose_purpose_notice(uma)
        self.assertEqual(uma, duas)

    def test_endpoint_de_campanha_usa_a_composicao(self):
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn("lgpd_registry.compose_purpose_notice", fonte)


class DocumentoParaRIPDTests(unittest.TestCase):
    def test_documento_lista_todas_as_operacoes(self):
        doc = R.registry_as_document()
        self.assertEqual(len(doc["operacoes"]), len(R.OPERACOES))
        self.assertTrue(doc["versao"])


if __name__ == "__main__":
    unittest.main()
