"""froid_nr1_required_sample() contra a implementacao em Python.

O SQL e a autoridade do Portao A: froid_nr1_dimension_scores nao consulta o
Python para nada. O modulo nr1_compliance so existe para a tela dizer quanto
falta sem ida e volta ao banco. Se os dois divergirem, o painel promete um
numero e o portao exige outro — e o gestor persegue uma meta que nao libera
nada.

Os testes em Python cobrem a formula; nao conseguem cobrir a aritmetica do
Postgres, que e onde estao os riscos reais desta funcao: numeric contra float,
ceil sobre numeric, e a comparacao do corte de censo antes do arredondamento.
Por isso este arquivo compara os dois lados chamando ambos.

Pulado automaticamente quando ``FROID_TEST_DATABASE_URL`` nao esta definido.

Para rodar:
    FROID_TEST_DATABASE_URL=postgresql://... python -m unittest \\
        tests.test_nr1_representatividade_postgres
"""

import os
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from nr1_compliance import required_sample  # noqa: E402

DATABASE_URL = os.getenv("FROID_TEST_DATABASE_URL", "")

try:  # pragma: no cover - import guard
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class RequiredSampleEspelhaOPython(unittest.TestCase):
    @classmethod
    def connect(cls):
        return psycopg.connect(DATABASE_URL, autocommit=True)

    @classmethod
    def setUpClass(cls):
        with cls.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regprocedure('froid_nr1_required_sample"
                "(integer,numeric,numeric,numeric)') IS NOT NULL"
            )
            if not cursor.fetchone()[0]:
                raise unittest.SkipTest(
                    "migration 025 nao aplicada neste banco de teste"
                )

    def sql_required(self, population, **kwargs):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT froid_nr1_required_sample(%s,%s,%s,%s)",
                (
                    population,
                    kwargs.get("margin_of_error"),
                    kwargs.get("confidence_z"),
                    kwargs.get("census_threshold"),
                ),
            )
            return cursor.fetchone()[0]

    def test_padrao_da_plataforma_bate_em_toda_a_faixa(self):
        populacoes = list(range(1, 200)) + [
            250, 300, 500, 1000, 3000, 10000, 50000, 250000
        ]
        for populacao in populacoes:
            with self.subTest(populacao=populacao):
                self.assertEqual(
                    self.sql_required(populacao), required_sample(populacao)
                )

    def test_parametros_alternativos_batem(self):
        # Um cliente cuja consultoria de SST trabalhe com outra tolerancia muda
        # o dado, e os dois lados precisam continuar concordando.
        for margem, z, censo in (
            (0.10, 1.96, 0.80),
            (0.03, 2.576, 0.80),
            (0.05, 1.645, 0.90),
            (0.05, 1.96, 1.00),
        ):
            for populacao in (30, 97, 98, 150, 1000, 5000):
                with self.subTest(margem=margem, z=z, censo=censo, n=populacao):
                    self.assertEqual(
                        self.sql_required(
                            populacao,
                            margin_of_error=margem,
                            confidence_z=z,
                            census_threshold=censo,
                        ),
                        required_sample(
                            populacao,
                            margin_of_error=margem,
                            confidence_z=z,
                            census_threshold=censo,
                        ),
                    )

    def test_efetivo_nao_declarado_devolve_nulo(self):
        # NULL e o que faz o portao reprovar. Zero aqui liberaria tudo.
        for populacao in (0, -1, None):
            with self.subTest(populacao=populacao):
                self.assertIsNone(self.sql_required(populacao))

    def test_nulo_reprova_na_comparacao(self):
        # A razao de o chamador precisar testar IS NULL explicitamente: em SQL
        # "10 < NULL" nao e falso, e NULL — um IF sozinho deixaria passar.
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 10 < froid_nr1_required_sample(0)")
            self.assertIsNone(cursor.fetchone()[0])
            cursor.execute("SELECT 10 >= froid_nr1_required_sample(0)")
            self.assertIsNone(cursor.fetchone()[0])

    def test_parametros_invalidos_levantam(self):
        for kwargs in (
            {"margin_of_error": 0},
            {"margin_of_error": 1},
            {"confidence_z": 0},
            {"census_threshold": 1.5},
        ):
            with self.subTest(**kwargs):
                with self.assertRaises(psycopg.errors.RaiseException):
                    self.sql_required(500, **kwargs)


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class EfetivoObrigatorioParaAbrir(unittest.TestCase):
    """O gatilho da 025 sobre enforce_campaign_open_requirements."""

    @classmethod
    def connect(cls):
        return psycopg.connect(DATABASE_URL, autocommit=True)

    def test_mensagem_do_gatilho_esta_registrada(self):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT prosrc FROM pg_proc "
                "WHERE proname = 'enforce_campaign_open_requirements'"
            )
            linha = cursor.fetchone()
            if not linha:
                self.skipTest("migration 013 nao aplicada neste banco de teste")
            corpo = linha[0]
            self.assertIn("target_headcount", corpo)
            self.assertIn("efetivo de trabalhadores declarado", corpo)
            # As exigencias da 013 nao podem ter sido perdidas na reescrita.
            self.assertIn("canal de apoio", corpo)
            self.assertIn("aviso de finalidade", corpo)


if __name__ == "__main__":
    unittest.main()
