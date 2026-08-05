"""A validity study that cannot flatter itself.

Every test here exists because the corresponding shortcut is the easy one to
take when a number is needed for a slide.
"""

import os
import random
import sys
import unittest
from math import sqrt
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import froid_validation as V  # noqa: E402


def amostra_correlacionada(n: int, r_alvo: float, semente: int = 7):
    """Duas listas com correlação aproximadamente r_alvo."""
    rng = random.Random(semente)
    xs, ys = [], []
    for _ in range(n):
        base = rng.gauss(0, 1)
        ruido = rng.gauss(0, 1)
        xs.append(base)
        ys.append(r_alvo * base + sqrt(max(0.0, 1 - r_alvo ** 2)) * ruido)
    return xs, ys


class CoeficienteTests(unittest.TestCase):
    def test_recupera_correlacao_conhecida(self):
        xs, ys = amostra_correlacionada(400, 0.6)
        r = V.pearson_r(xs, ys)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r, 0.6, delta=0.08)

    def test_relacao_perfeita_e_um(self):
        xs = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(V.pearson_r(xs, [2, 4, 6, 8, 10]), 1.0, places=6)
        self.assertAlmostEqual(V.pearson_r(xs, [10, 8, 6, 4, 2]), -1.0, places=6)

    def test_lado_constante_nao_vira_correlacao_zero(self):
        # Zero sugeriria ausência medida de relação. A amostra é inutilizável,
        # e são coisas diferentes.
        self.assertIsNone(V.pearson_r([1, 2, 3, 4], [5, 5, 5, 5]))

    def test_intervalo_encolhe_com_a_amostra(self):
        estreito = V.fisher_interval(0.5, 400)
        largo = V.fisher_interval(0.5, 35)
        self.assertLess(estreito[1] - estreito[0], largo[1] - largo[0])


class PosturaConservadoraTests(unittest.TestCase):
    """O veredito sai da extremidade do intervalo, nunca do ponto."""

    def setUp(self):
        self.par = V.Pairing("psychomotor_slowing", "PHQ-9", +1)

    def test_amostra_pequena_nao_produz_coeficiente(self):
        xs, ys = amostra_correlacionada(12, 0.9)
        r = V.evaluate(self.par, xs, ys)
        self.assertEqual(r.verdict, "insufficient_sample")
        self.assertIsNone(r.r)
        self.assertFalse(r.reportable)
        self.assertIn(str(V.MIN_PAIRS), r.detail)

    def test_correlacao_alta_com_intervalo_tocando_zero_nao_e_convergencia(self):
        # O ponto estimado pode parecer excelente; se o intervalo cruza o zero,
        # a amostra não distingue relação de ausência de relação.
        xs, ys = amostra_correlacionada(31, 0.0, semente=3)
        r = V.evaluate(self.par, xs, ys)
        if r.interval and r.interval[0] <= 0 <= r.interval[1]:
            self.assertEqual(r.verdict, "inconclusive")

    def test_convergencia_forte_exige_limite_conservador_alto(self):
        xs, ys = amostra_correlacionada(600, 0.7)
        r = V.evaluate(self.par, xs, ys)
        self.assertEqual(r.verdict, "strong")
        self.assertGreaterEqual(r.interval[0], V.R_STRONG)

    def test_direcao_contraria_a_declarada_e_evidencia_contra(self):
        # A hipótese declarada é +1. Uma correlação forte no sentido oposto não
        # é um achado a reinterpretar: é evidência contra a convergência.
        xs, ys = amostra_correlacionada(400, -0.6)
        r = V.evaluate(self.par, xs, ys)
        self.assertEqual(r.verdict, "contradicted")
        self.assertIn("oposto", r.detail)

    def test_direcao_negativa_declarada_aceita_correlacao_negativa(self):
        par = V.Pairing("prosodic_activation", "PHQ-9", -1)
        xs, ys = amostra_correlacionada(600, -0.7)
        r = V.evaluate(par, xs, ys)
        self.assertEqual(r.verdict, "strong")


class FraseDivulgavelTests(unittest.TestCase):
    """O que pode ser dito fora, e nada além disso."""

    def test_amostra_insuficiente_diz_que_nao_ha_evidencia(self):
        xs, ys = amostra_correlacionada(10, 0.9)
        frase = V.evidence_statement(
            V.evaluate(V.DECLARED_PAIRINGS[0], xs, ys)
        )
        self.assertIn("Ainda nao ha evidencia", frase)

    def test_resultado_forte_nao_autoriza_uso_diagnostico(self):
        xs, ys = amostra_correlacionada(600, 0.7)
        frase = V.evidence_statement(V.evaluate(V.DECLARED_PAIRINGS[0], xs, ys))
        self.assertIn("IC 95%", frase)
        self.assertIn("Nao substitui o instrumento", frase)
        self.assertIn("autoriza uso diagnostico", frase.lower())

    def test_nenhuma_frase_afirma_validacao_concluida(self):
        for r_alvo, n in ((0.7, 600), (0.2, 100), (-0.6, 400)):
            xs, ys = amostra_correlacionada(n, r_alvo)
            frase = V.evidence_statement(
                V.evaluate(V.DECLARED_PAIRINGS[0], xs, ys)
            ).lower()
            for proibido in ("validado", "comprovado", "equivale ao", "substitui o phq"):
                self.assertNotIn(proibido, frase)


class HipoteseDeclaradaTests(unittest.TestCase):
    def test_direcao_invalida_e_recusada(self):
        with self.assertRaises(ValueError):
            V.Pairing("x", "PHQ-9", 0)

    def test_pares_declarados_tem_direcao_explicita(self):
        self.assertTrue(V.DECLARED_PAIRINGS)
        for par in V.DECLARED_PAIRINGS:
            self.assertIn(par.expected_direction, (1, -1))

    def test_run_declared_ignora_par_sem_amostra(self):
        xs, ys = amostra_correlacionada(600, 0.7)
        resultados = V.run_declared([("psychomotor_slowing:PHQ-9", xs, ys)])
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0].instrument, "PHQ-9")


class MigrationTests(unittest.TestCase):
    """Garantias que precisam morar no banco, e não numa convenção."""

    def setUp(self):
        self.sql = (SERVER_DIR / "migrations" / "018_convergent_validity.sql").read_text(
            encoding="utf-8"
        )

    def test_consentimento_e_condicao_de_existencia_da_linha(self):
        # Sem o CHECK, a linha sem consentimento existe e depende de toda
        # consulta futura lembrar de filtrar.
        self.assertIn("CHECK (research_consent = TRUE)", self.sql)

    def test_nao_guarda_resposta_de_item_do_instrumento(self):
        # Guardar item a item faria do FROID o aplicador do instrumento.
        self.assertNotIn("item_response", self.sql)
        self.assertIn("total_score", self.sql)

    def test_pares_excluem_janela_de_qualidade_ruim(self):
        self.assertIn("o.coverage >= 0.80", self.sql)
        self.assertIn("o.confidence >= 0.70", self.sql)

    def test_pares_nao_expoem_identificador_de_paciente(self):
        inicio = self.sql.index("CREATE OR REPLACE FUNCTION froid_validation_pairs")
        corpo = self.sql[inicio:]
        self.assertNotIn("patient_id", corpo)

    def test_rls_ativa_nas_duas_tabelas(self):
        for tabela in ("validation_administrations", "validation_observations"):
            self.assertIn(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY", self.sql)


class DoisEstagiosTests(unittest.TestCase):
    """Piloto e estudo confirmatorio sao coisas diferentes, e a diferenca e
    aritmetica: com r verdadeiro de 0,50 o limite conservador nao alcanca a
    faixa moderada em 30 pares, e alcanca em 70."""

    def test_piloto_nao_sai_como_resultado(self):
        xs, ys = amostra_correlacionada(V.PILOT_PAIRS, 0.75)
        r = V.evaluate(V.DECLARED_PAIRINGS[0], xs, ys)
        self.assertTrue(r.is_pilot)
        self.assertFalse(r.is_final)
        self.assertEqual(r.stage, "piloto")
        frase = V.evidence_statement(r)
        self.assertIn("PILOTO", frase)
        self.assertIn("Nao divulgar", frase)

    def test_antes_do_piloto_o_alvo_exibido_e_o_piloto(self):
        # Abaixo do piso nao sai coeficiente nenhum, e a tela precisa mostrar
        # quanto falta para o marco seguinte — que e o piloto, nao os 70.
        xs, ys = amostra_correlacionada(20, 0.5)
        r = V.evaluate(V.DECLARED_PAIRINGS[0], xs, ys)
        self.assertEqual(r.stage, "coleta")
        self.assertEqual(r.progress, f"20/{V.PILOT_PAIRS}")
        self.assertIsNone(r.r)

    def test_amostra_confirmatoria_libera_a_conclusao(self):
        xs, ys = amostra_correlacionada(V.TARGET_PAIRS, 0.75)
        r = V.evaluate(V.DECLARED_PAIRINGS[0], xs, ys)
        self.assertTrue(r.is_final)
        self.assertEqual(r.stage, "confirmatorio")
        self.assertIn("compativel com validade convergente", V.evidence_statement(r))

    def test_o_intervalo_em_trinta_e_largo_demais_para_afirmar(self):
        # A razao de existirem dois estagios, verificada e nao suposta.
        largura_30 = V.fisher_interval(0.5, 30)
        largura_70 = V.fisher_interval(0.5, 70)
        self.assertLess(largura_30[0], V.R_MODERATE)
        self.assertGreaterEqual(largura_70[0], V.R_MODERATE)

    def test_estagios_em_ordem(self):
        self.assertLess(V.MIN_PAIRS, V.TARGET_PAIRS)
        self.assertLessEqual(V.MIN_PAIRS, V.PILOT_PAIRS)
        self.assertLess(V.PILOT_PAIRS, V.TARGET_PAIRS)


class UmInstrumentoSoTests(unittest.TestCase):
    """Dois questionarios por sessao e onde a adesao morre — e ela morre de um
    jeito pior que o incomodo: o profissional pula quando a sessao correu longa
    ou o paciente estava mal, que sao justamente as sessoes com sinal."""

    def test_todas_as_hipoteses_ativas_usam_o_mesmo_instrumento(self):
        instrumentos = {p.instrument for p in V.DECLARED_PAIRINGS}
        self.assertEqual(len(instrumentos), 1, instrumentos)
        self.assertEqual(instrumentos, {"PHQ-9"})

    def test_a_hipotese_adiada_esta_registrada_e_nao_apagada(self):
        self.assertTrue(V.STAGE_TWO_PAIRINGS)
        adiadas = {p.instrument for p in V.STAGE_TWO_PAIRINGS}
        self.assertEqual(adiadas, {"GAD-7"})

    def test_nenhuma_hipotese_aparece_nos_dois_estagios(self):
        ativas = {(p.pattern_key, p.instrument) for p in V.DECLARED_PAIRINGS}
        adiadas = {(p.pattern_key, p.instrument) for p in V.STAGE_TWO_PAIRINGS}
        self.assertEqual(ativas & adiadas, set())


class TCLEPesquisaTests(unittest.TestCase):
    """O consentimento de pesquisa nao pode se confundir com o clinico.

    Um paciente que recusa pesquisa tem de receber o produto clinico inteiro.
    Se a recusa custar atendimento, o consentimento deixa de ser livre — e um
    consentimento nao livre nao vale nada, nem eticamente nem juridicamente.
    """

    def setUp(self):
        import legal_documents

        self.doc = legal_documents.DOCUMENT_TEMPLATES["research_tcle"]
        self.texto = " ".join(corpo for _, corpo in self.doc["sections"]).lower()

    def test_e_documento_proprio_e_nao_parte_do_tcle_clinico(self):
        import legal_documents

        self.assertNotIn(
            "research_tcle", legal_documents.required_document_keys("professional")
        )
        self.assertNotIn(
            "research_tcle", legal_documents.required_document_keys("organization")
        )

    def test_diz_que_recusar_nao_afeta_o_atendimento(self):
        self.assertIn("recusar nao muda nada no seu atendimento",
                      self.texto.replace("ã", "a").replace("é", "e"))

    def test_preve_revogacao_e_o_que_acontece_com_o_ja_coletado(self):
        self.assertIn("retirar sua participa", self.texto)
        self.assertIn("eliminados da base do estudo", self.texto)
        # Prometer desfazer o publicado seria promessa impossivel.
        self.assertIn("nao podem ser desfeitos",
                      self.texto.replace("ã", "a").replace("é", "e"))

    def test_promete_divulgar_resultado_contrario_a_hipotese(self):
        self.assertIn("inclusive se contrariarem", self.texto)

    def test_declara_que_o_froid_nao_aplica_o_questionario(self):
        self.assertIn("aplicado e interpretado pelo profissional", self.texto)

    def test_nao_usa_fala_transcricao_nem_prontuario(self):
        for termo in ("transcri", "prontuario"):
            self.assertIn(termo, self.texto.replace("á", "a"))
        self.assertIn("nao sao usados", self.texto.replace("ã", "a"))

class ConsentimentoRevogavelTests(unittest.TestCase):
    """A promessa do TCLE precisa ser uma funcao, nao um paragrafo."""

    def setUp(self):
        self.sql = (
            SERVER_DIR / "migrations" / "019_research_consent_state.sql"
        ).read_text(encoding="utf-8")

    def test_revogacao_apaga_os_pares_de_verdade(self):
        self.assertIn("DELETE FROM validation_administrations", self.sql)
        self.assertIn("froid_revoke_research_consent", self.sql)

    def test_estado_nunca_e_concedido_e_revogado_ao_mesmo_tempo(self):
        self.assertIn("patient_research_consent_state CHECK", self.sql)

    def test_ausencia_de_registro_significa_nunca_perguntado(self):
        # COALESCE para FALSE: sem linha, nao ha consentimento — e nao um
        # default permissivo.
        self.assertIn("COALESCE(", self.sql)
        self.assertIn("FALSE", self.sql)

    def test_progresso_nao_devolve_coeficiente_nem_identidade(self):
        inicio = self.sql.index("CREATE OR REPLACE FUNCTION froid_validation_progress")
        corpo = self.sql[inicio:]
        self.assertNotIn("patient_id", corpo)
        self.assertNotIn("total_score", corpo)
        self.assertIn("count(*)", corpo)

    def test_progresso_aplica_os_mesmos_pisos_de_qualidade(self):
        inicio = self.sql.index("CREATE OR REPLACE FUNCTION froid_validation_progress")
        corpo = self.sql[inicio:]
        self.assertIn("o.coverage >= 0.80", corpo)
        self.assertIn("o.confidence >= 0.70", corpo)

    def test_rls_ativa_e_usa_a_variavel_do_tenant_store(self):
        self.assertIn(
            "ALTER TABLE patient_research_consent ENABLE ROW LEVEL SECURITY", self.sql
        )
        self.assertIn("current_setting('app.organization_id'", self.sql)

class TravaDoComiteDeEticaTests(unittest.TestCase):
    """Coleta antes do parecer nao e irregularidade abstrata: sao 70 pares que
    nao valem, descobertos seis meses depois."""

    def setUp(self):
        self._antes = os.environ.get("FROID_RESEARCH_CAAE")

    def tearDown(self):
        if self._antes is None:
            os.environ.pop("FROID_RESEARCH_CAAE", None)
        else:
            os.environ["FROID_RESEARCH_CAAE"] = self._antes

    def test_sem_caae_a_coleta_esta_bloqueada(self):
        os.environ.pop("FROID_RESEARCH_CAAE", None)
        self.assertFalse(V.collection_allowed())
        self.assertEqual(V.ethics_approval(), "")

    def test_caae_em_branco_nao_libera(self):
        os.environ["FROID_RESEARCH_CAAE"] = "   "
        self.assertFalse(V.collection_allowed())

    def test_com_caae_a_coleta_e_liberada(self):
        os.environ["FROID_RESEARCH_CAAE"] = "12345678.9.0000.5678"
        self.assertTrue(V.collection_allowed())
        self.assertEqual(V.ethics_approval(), "12345678.9.0000.5678")

    def test_os_dois_endpoints_de_escrita_consultam_a_trava(self):
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        inicio = fonte.index("async def set_research_consent")
        fim = fonte.index("async def read_validation_history")
        trecho = fonte[inicio:fim]
        self.assertEqual(trecho.count("collection_allowed()"), 2, trecho.count("x"))

if __name__ == "__main__":
    unittest.main()
