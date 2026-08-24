"""Portao A: a coorte precisa falar pelo efetivo.

O piso que existia antes contava cabecas em termos absolutos e nunca olhava o
tamanho da empresa. Estes testes cobrem o portao novo pelo que ele precisa
garantir, e nao pelos numeros que hoje sao o padrao: a formula continua valendo
se o cliente mudar a tolerancia, entao quase tudo aqui e propriedade, e as
poucas asserçoes de valor literal existem porque o numero vai parar num
documento que a fiscalizacao le.

Uma classe testa a nao-regressao da tabela publicada; outra, a independencia
entre este portao e o de anonimato, que e o erro mais provavel de alguem
cometer ao mexer nisto depois.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from nr1_compliance import (  # noqa: E402
    CENSUS_THRESHOLD,
    CONFIDENCE_Z,
    MARGIN_OF_ERROR,
    MIN_COHORT_CUT,
    MIN_COHORT_TOTAL,
    campaign_is_reportable,
    representativeness,
    representativeness_notice,
    required_sample,
)

MIGRATION = SERVER_DIR / "migrations" / "025_representativeness_floor.sql"

# Primeiro efetivo, no padrao 95%/5pp, em que a amostra deixa de alcancar 80% do
# quadro e o questionario volta a ser amostragem em vez de censo.
PRIMEIRA_AMOSTRA = 98


class AmostraExigida(unittest.TestCase):
    """A tabela que vai para o documento de criterios."""

    # Amostra para proporcao com correcao de populacao finita, 95% / 5pp,
    # p=0,5. Conferida a mao antes de virar teste.
    PUBLICADA = {
        3000: 341,
        1000: 278,
        500: 218,
        300: 169,
        200: 132,
        150: 109,
        100: 80,
    }

    def test_valores_publicados(self):
        for populacao, esperado in self.PUBLICADA.items():
            with self.subTest(populacao=populacao):
                self.assertEqual(required_sample(populacao), esperado)

    def test_nunca_pede_mais_do_que_existe(self):
        for populacao in range(1, 400):
            with self.subTest(populacao=populacao):
                self.assertLessEqual(required_sample(populacao), populacao)

    def test_cresce_com_a_populacao_dentro_do_regime_de_amostra(self):
        anterior = 0
        for populacao in range(PRIMEIRA_AMOSTRA, 4000):
            atual = required_sample(populacao)
            with self.subTest(populacao=populacao):
                self.assertGreaterEqual(atual, anterior)
            anterior = atual

    def test_margem_menor_exige_mais(self):
        folgada = required_sample(3000, margin_of_error=0.10)
        apertada = required_sample(3000, margin_of_error=0.05)
        self.assertLess(folgada, apertada)

    def test_parametros_fora_da_faixa_sao_recusados(self):
        for kwargs in (
            {"margin_of_error": 0.0},
            {"margin_of_error": 1.0},
            {"confidence_z": 0.0},
            {"census_threshold": 0.0},
            {"census_threshold": 1.5},
        ):
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    required_sample(500, **kwargs)


class TransicaoParaCenso(unittest.TestCase):
    """Onde o questionario deixa de ser o instrumento adequado."""

    def test_grupo_pequeno_vira_censo(self):
        for populacao in (1, 5, 20, 50, 80, 90, PRIMEIRA_AMOSTRA - 1):
            with self.subTest(populacao=populacao):
                self.assertEqual(required_sample(populacao), populacao)
                self.assertEqual(representativeness(populacao, 0).mode, "census")

    def test_cem_pessoas_ainda_e_amostra(self):
        self.assertEqual(required_sample(100), 80)
        self.assertEqual(representativeness(100, 0).mode, "sample")

    def test_a_transicao_acontece_uma_unica_vez(self):
        """Regressao: a exigencia oscilava em torno do corte.

        Comparar contra a fracao de corte o inteiro JA arredondado fazia o teto
        empurrar populacoes vizinhas para lados opostos — 100 pedia amostra de
        80, 101 pedia censo de 101, 102 voltava a pedir amostra de 81. Quem
        tivesse 101 pessoas no quadro era punido por declarar uma a mais que o
        vizinho. A decisao passou a ser tomada sobre o valor continuo.
        """
        modos = ["census" if required_sample(n) == n else "sample" for n in range(1, 5000)]
        trocas = [n for n in range(1, len(modos)) if modos[n] != modos[n - 1]]
        self.assertEqual(len(trocas), 1, f"transicoes de regime em N={trocas}")
        self.assertEqual(trocas[0] + 1, PRIMEIRA_AMOSTRA)

    def test_a_descontinuidade_do_censo_e_conhecida(self):
        """O salto na fronteira e aceito, e vale saber por que.

        Um efetivo de 97 exige 97 respostas e um de 98 exige 79: a exigencia
        absoluta cai ao cruzar a fronteira. Isso e inerente a qualquer corte de
        censo e nao um defeito — do lado de baixo o questionario nao e o
        instrumento indicado, e e ali que o Guia MTE manda usar dialogo e
        observacao. O incentivo a superdeclarar o quadro para escapar do censo
        existe, mas cobra caro: efetivo declarado que nao bate com S-2200/S-2210
        e exatamente a inconsistencia que a fiscalizacao procura no eSocial.
        """
        self.assertGreater(
            required_sample(PRIMEIRA_AMOSTRA - 1), required_sample(PRIMEIRA_AMOSTRA)
        )

    def test_corte_de_censo_e_configuravel(self):
        # Com um corte mais alto a mesma populacao volta a ser amostra.
        self.assertEqual(required_sample(90), 90)
        self.assertLess(required_sample(90, census_threshold=1.0), 90)


class EfetivoNaoDeclarado(unittest.TestCase):
    """Zero nao pode ser o atalho para desligar o portao."""

    def test_sem_populacao_nao_ha_amostra(self):
        self.assertIsNone(required_sample(0))
        self.assertIsNone(required_sample(-10))
        self.assertIsNone(required_sample(None))

    def test_veredito_reprova_e_se_explica(self):
        veredito = representativeness(0, 5000)
        self.assertEqual(veredito.mode, "undeclared")
        self.assertFalse(veredito.met)
        self.assertIsNone(veredito.required)
        self.assertIn("não foi declarado", representativeness_notice(veredito))

    def test_muitas_respostas_nao_compensam_efetivo_ausente(self):
        # O contrario seria o buraco: coletar muito e declarar nada.
        self.assertFalse(representativeness(0, 100000).met)


class Veredito(unittest.TestCase):
    def test_atinge_no_numero_exato(self):
        self.assertTrue(representativeness(3000, 341).met)
        self.assertFalse(representativeness(3000, 340).met)

    def test_confianca_corresponde_ao_z(self):
        self.assertAlmostEqual(representativeness(100, 0).confidence, 0.95, places=3)
        self.assertAlmostEqual(
            representativeness(100, 0, confidence_z=2.576).confidence, 0.99, places=3
        )

    def test_veredito_atingido_nao_produz_aviso(self):
        self.assertEqual(representativeness_notice(representativeness(3000, 341)), "")

    def test_aviso_de_amostra_diz_quanto_falta(self):
        aviso = representativeness_notice(representativeness(3000, 200))
        self.assertIn("200", aviso)
        self.assertIn("341", aviso)
        self.assertIn("3000", aviso)

    def test_aviso_de_censo_nomeia_o_caminho_alternativo(self):
        aviso = representativeness_notice(representativeness(40, 30))
        self.assertIn("censo", aviso)
        self.assertIn("Guia MTE", aviso)

    def test_aviso_cita_a_tolerancia_configurada(self):
        # Citar 95% quando a organizacao configurou 99% seria informacao errada
        # num texto que acompanha documento de fiscalizacao.
        aviso = representativeness_notice(
            representativeness(3000, 10, confidence_z=2.576, margin_of_error=0.03)
        )
        self.assertIn("99%", aviso)
        self.assertIn("3 pontos", aviso)


class DoisPortoesIndependentes(unittest.TestCase):
    """O erro mais provavel de quem mexer nisto e fundir os dois pisos."""

    def test_anonimato_reprova_onde_representatividade_aprova(self):
        # Setor de 9 pessoas: censo alcancado, e ainda assim coorte pequena
        # demais para nao reidentificar quem respondeu.
        #
        # Este teste usava 15 e parou de valer quando a migration 027 baixou o
        # piso de campanha para esse numero. A propriedade que ele existe para
        # provar nao mudou — os dois portoes reprovam por motivos diferentes —
        # mas o exemplo tinha de descer junto com o piso.
        veredito = representativeness(9, 9)
        self.assertTrue(veredito.met)
        self.assertFalse(campaign_is_reportable(9))

    def test_representatividade_reprova_onde_anonimato_aprova(self):
        # Empresa de 3.000 com 200 respostas: folgado no anonimato, longe da
        # amostra.
        self.assertTrue(campaign_is_reportable(200))
        self.assertFalse(representativeness(3000, 200).met)

    def test_pisos_de_anonimato_seguem_absolutos(self):
        """Nenhum dos dois pode passar a depender do efetivo declarado.

        Este teste fixava os valores 50 e 10 e, com isso, transformava qualquer
        revisao de politica em falha de teste — inclusive uma revisao correta.
        O que ele precisa guardar nao e o numero: e que o portao de anonimato
        conte cabecas e so, sem consultar o quadro da empresa. Piso que varia
        com o efetivo declarado deixa de ser piso de anonimato e vira uma
        segunda copia, pior, do portao de representatividade.
        """
        for respostas in (0, 1, 9, 14, 15, 40, 3000):
            with self.subTest(respostas=respostas):
                self.assertEqual(
                    campaign_is_reportable(respostas), respostas >= MIN_COHORT_TOTAL
                )

    def test_o_piso_que_protege_pessoa_nao_se_moveu(self):
        """MIN_COHORT_CUT e o unico dos dois que decide tamanho de coorte.

        A migration 027 baixou o piso de CAMPANHA, que diz quanta resposta o
        conjunto precisa somar. O piso de RECORTE decide quao pequeno pode ser
        um grupo publicado, que e o numero de que depende a reidentificacao, e
        continua em 10. Confundir os dois foi o que manteve empresas de 10 a 49
        trabalhadores fora do modulo sem que isso protegesse ninguem.
        """
        self.assertEqual(MIN_COHORT_CUT, 10)
        self.assertGreaterEqual(MIN_COHORT_TOTAL, MIN_COHORT_CUT)

    def test_o_piso_novo_nao_dispensa_a_representatividade(self):
        """Uma campanha rala em empresa grande continua sem publicar.

        O piso de 15 e o que abre a porta das empresas pequenas. Se ele tambem
        passasse a valer como suficiencia, uma empresa de 3.000 pessoas com 15
        respostas geraria inventario sobre 0,5% do quadro — que e exatamente o
        buraco que a migration 025 fechou.
        """
        self.assertTrue(campaign_is_reportable(15))
        self.assertFalse(representativeness(3000, 15).met)
        self.assertFalse(representativeness(200, 15).met)
        # E na faixa que a 027 abriu, o censo continua sendo a exigencia.
        self.assertTrue(representativeness(15, 15).met)
        self.assertFalse(representativeness(15, 14).met)


class EspelhoDoSql(unittest.TestCase):
    """SQL decide; o Python explica. Se divergirem, a tela mente.

    O banco e a autoridade — froid_nr1_dimension_scores nao consulta o Python
    para nada. Estas constantes existem para a API dizer quanto falta sem ida e
    volta, e um valor diferente aqui produz uma tela que promete um numero e um
    portao que exige outro.
    """

    def setUp(self):
        self.sql = MIGRATION.read_text(encoding="utf-8")

    def _literal(self, funcao: str) -> float:
        achado = re.search(
            rf"FUNCTION {funcao}\(\) RETURNS numeric\s*\nLANGUAGE sql IMMUTABLE AS \$\$ SELECT ([0-9.]+)",
            self.sql,
        )
        self.assertIsNotNone(achado, f"{funcao} nao encontrada na migration")
        return float(achado.group(1))

    def test_z_confere(self):
        self.assertEqual(self._literal("froid_nr1_sampling_confidence_z"), CONFIDENCE_Z)

    def test_margem_confere(self):
        self.assertEqual(self._literal("froid_nr1_sampling_margin"), MARGIN_OF_ERROR)

    def test_corte_de_censo_confere(self):
        self.assertEqual(self._literal("froid_nr1_census_threshold"), CENSUS_THRESHOLD)

    def test_efetivo_e_condicao_de_abertura(self):
        self.assertIn("sem o efetivo de trabalhadores declarado", self.sql)

    def test_portao_reprova_com_efetivo_nulo(self):
        # required_total NULL precisa reprovar explicitamente: "total < NULL" e
        # NULL, e um IF que nao dispara deixaria a campanha passar.
        self.assertIn("IF required_total IS NULL OR campaign_total < required_total", self.sql)


class OPisoDeCampanhaDesce(unittest.TestCase):
    """migration 027: de 50 para 15, e nada mais se move.

    A faixa de 10 a 49 trabalhadores era a unica em que o piso de 50 ainda tinha
    efeito, e ali ele nao protegia ninguem: a amostra exigida nesse tamanho ja e
    o censo, entao a representatividade sozinha ja pedia todo mundo. O que o
    piso acrescentava era impossibilidade aritmetica — uma empresa de 30 pessoas
    nunca reune 50 respostas, ainda que todas respondam.
    """

    @classmethod
    def setUpClass(cls):
        cls.sql = (
            SERVER_DIR / "migrations" / "027_campaign_floor_fifteen.sql"
        ).read_text(encoding="utf-8")
        # So o que o banco executa. Uma migration cujo cabecalho explica por que
        # NAO mexe em representatividade cita a funcao pelo nome — e um teste
        # que lesse a prosa concluiria o contrario do que ela afirma.
        cls.executavel = "\n".join(
            linha
            for linha in cls.sql.splitlines()
            if not linha.lstrip().startswith("--")
        )

    def test_a_migration_redefine_apenas_o_piso_de_campanha(self):
        self.assertIn("froid_nr1_min_cohort_total() RETURNS integer", self.executavel)
        self.assertIn("SELECT 15", self.executavel)
        # O piso de recorte nao pode ser tocado aqui: e ele que decide o tamanho
        # minimo de um grupo publicado, que e o numero de que a reidentificacao
        # depende. Redefini-lo junto seria o erro silencioso desta mudanca.
        self.assertNotIn(
            "CREATE OR REPLACE FUNCTION froid_nr1_min_cohort_cut", self.executavel
        )
        self.assertNotIn("froid_nr1_required_sample", self.executavel)
        self.assertNotIn("froid_nr1_dimension_scores", self.executavel)

    def test_a_migration_recusa_piso_de_campanha_abaixo_do_de_recorte(self):
        """Incoerencia que liberaria campanha que nenhum recorte pode publicar.

        A verificacao roda na migration, e nao em tempo de consulta: quem editar
        um dos dois numeros descobre no deploy, e nao servindo resultado torto.
        """
        self.assertIn("RAISE EXCEPTION", self.sql)
        self.assertIn(
            "froid_nr1_min_cohort_total() < froid_nr1_min_cohort_cut()", self.sql
        )

    def test_a_faixa_aberta_entra_por_censo_e_nao_por_desconto(self):
        """De 15 a 49 a exigencia continua sendo todo mundo.

        O que a reducao concede e o direito de tentar. Confundir isso com um
        desconto na amostra e o mal-entendido que a proposta comercial precisa
        evitar, porque nessa faixa uma unica recusa suspende o inventario.
        """
        for efetivo in (15, 20, 30, 49):
            with self.subTest(efetivo=efetivo):
                self.assertEqual(required_sample(efetivo), efetivo)
                self.assertTrue(campaign_is_reportable(efetivo))
                self.assertFalse(representativeness(efetivo, efetivo - 1).met)

    def test_abaixo_de_quinze_nenhuma_campanha_publica(self):
        for respostas in (0, 1, 9, 14):
            with self.subTest(respostas=respostas):
                self.assertFalse(campaign_is_reportable(respostas))

    def test_a_ordem_importou_e_a_faixa_veio_antes(self):
        """A reducao so e segura porque a proporcao ja sai em faixa.

        Se o painel voltasse a publicar critical_ratio exato ao lado do tamanho
        da coorte, uma multiplicacao devolveria a contagem de pessoas — e numa
        empresa de 15 isso esta a um passo de um nome. Este teste amarra as duas
        mudancas para que desfazer a faixa quebre o piso junto.
        """
        import nr1_compliance

        self.assertTrue(hasattr(nr1_compliance, "critical_ratio_band"))
        painel = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        self.assertNotIn('"critical_ratio":', painel)
        # Em qualquer coorte a partir do piso de recorte, nenhuma e uma pessoa
        # continuam indistinguiveis.
        for n in range(MIN_COHORT_CUT, MIN_COHORT_TOTAL + 40):
            with self.subTest(coorte=n):
                self.assertEqual(
                    nr1_compliance.critical_ratio_band(0 / n)["label"],
                    nr1_compliance.critical_ratio_band(1 / n)["label"],
                )


if __name__ == "__main__":
    unittest.main()
