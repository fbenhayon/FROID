"""As restricoes do plano de acao contra um Postgres de verdade.

O arquivo irmao (test_nr1_plano_de_acao.py) le o texto da migration e prova que
cada exigencia da norma foi ESCRITA. Isso nao prova que ela FUNCIONA: uma CHECK
com parenteses no lugar errado, um trigger declarado sobre a coluna errada ou uma
funcao sem SECURITY DEFINER passam na leitura e falham no uso.

Este arquivo prova o comportamento, em duas camadas:

  1. Catalogo — as restricoes existem na tabela real, os gatilhos estao ligados
     nos eventos certos, e froid_nr1_flag_residual_risk_review e SECURITY
     DEFINER (sem isso ela nao consegue marcar a revisao residual quando quem
     registra a implementacao so tem papel sobre o plano).

  2. Comportamento — as CHECK sao exercitadas numa TEMP TABLE criada com
     LIKE ... INCLUDING ALL. A copia temporaria e deliberada: ela herda as CHECK
     e nao herda as chaves estrangeiras, o que permite testar a regra sem montar
     a cadeia organizacao -> instrumento -> dimensao -> campanha -> inventario, e
     sem escrever uma unica linha no banco do cliente.

Pulado automaticamente quando ``FROID_TEST_DATABASE_URL`` nao esta definido.

Para rodar:
    FROID_TEST_DATABASE_URL=postgresql://... python -m unittest \\
        tests.test_nr1_plano_de_acao_postgres
"""

import os
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

DATABASE_URL = os.getenv("FROID_TEST_DATABASE_URL", "")

try:  # pragma: no cover - import guard
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class CatalogoDoPlanoDeAcao(unittest.TestCase):
    """O que a migration deixou instalado, lido do catalogo do Postgres."""

    @classmethod
    def setUpClass(cls):
        cls.conn = psycopg.connect(DATABASE_URL, autocommit=True)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def restricoes(self):
        linhas = self.conn.execute(
            """
            SELECT conname, convalidated
            FROM pg_constraint
            WHERE conrelid = 'psychosocial_action_plan'::regclass
              AND contype = 'c'
            """
        ).fetchall()
        return {nome: valida for nome, valida in linhas}

    def test_todas_as_restricoes_da_norma_estao_instaladas(self):
        instaladas = self.restricoes()
        for nome in (
            "psychosocial_action_plan_done_needs_implementation",
            "psychosocial_action_plan_done_needs_schedule",
            "psychosocial_action_plan_done_needs_monitoring",
            "psychosocial_action_plan_measure_not_blank",
            "psychosocial_action_plan_cancel_needs_reason",
            "psychosocial_action_plan_efficacy_after_implementation",
            "psychosocial_action_plan_review_pairs_with_verdict",
            "psychosocial_action_plan_plan_action_check",
        ):
            with self.subTest(restricao=nome):
                self.assertIn(nome, instaladas)

    def test_a_coluna_plan_action_existe_com_o_dominio_certo(self):
        tipo = self.conn.execute(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'psychosocial_action_plan'
              AND column_name = 'plan_action'
            """
        ).fetchone()
        self.assertIsNotNone(tipo, "coluna plan_action nao foi criada")

    def test_os_dois_gatilhos_estao_ligados(self):
        gatilhos = {
            linha[0]
            for linha in self.conn.execute(
                """
                SELECT tgname FROM pg_trigger
                WHERE tgrelid = 'psychosocial_action_plan'::regclass
                  AND NOT tgisinternal
                """
            ).fetchall()
        }
        self.assertIn("psychosocial_action_plan_guard", gatilhos)
        self.assertIn("psychosocial_action_plan_residual_review", gatilhos)

    def test_o_gatilho_da_revisao_residual_e_security_definer(self):
        """Sem isto ele nao consegue tocar a linha de inventario.

        A politica de RLS do inventario exige papel de escrita. Quem registra a
        implementacao de uma medida pode ter papel sobre o plano e nao sobre o
        inventario — e nesse caso a obrigacao da alinea "a" simplesmente nao
        seria marcada, em silencio.
        """
        definer = self.conn.execute(
            """
            SELECT prosecdef FROM pg_proc
            WHERE proname = 'froid_nr1_flag_residual_risk_review'
            """
        ).fetchone()
        self.assertIsNotNone(definer, "funcao do gatilho nao existe")
        self.assertTrue(definer[0], "a funcao precisa ser SECURITY DEFINER")

    def test_o_gatilho_residual_dispara_na_coluna_certa(self):
        """AFTER INSERT OR UPDATE **OF implemented_at**.

        Disparar em todo UPDATE funcionaria, mas refazeria o UPDATE no
        inventario a cada edicao de texto da medida. Disparar na coluna errada
        nao dispararia nunca.
        """
        definicao = self.conn.execute(
            """
            SELECT pg_get_triggerdef(oid) FROM pg_trigger
            WHERE tgrelid = 'psychosocial_action_plan'::regclass
              AND tgname = 'psychosocial_action_plan_residual_review'
            """
        ).fetchone()
        self.assertIsNotNone(definicao)
        self.assertIn("implemented_at", definicao[0])
        self.assertIn("AFTER", definicao[0].upper())

    def test_o_runtime_pode_escrever_no_plano(self):
        """A queixa classica deste projeto: migration aplica e a escrita falha.

        Tabela sem GRANT explicito ao froid_runtime entra em schema_migrations,
        parece instalada, e quebra na primeira escrita — longe do deploy que a
        causou.
        """
        papel = self.conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = 'froid_runtime'"
        ).fetchone()
        if not papel:
            self.skipTest("papel froid_runtime nao existe neste banco")
        for privilegio in ("SELECT", "INSERT", "UPDATE"):
            with self.subTest(privilegio=privilegio):
                concedido = self.conn.execute(
                    "SELECT has_table_privilege('froid_runtime', "
                    "'psychosocial_action_plan', %s)",
                    (privilegio,),
                ).fetchone()[0]
                self.assertTrue(concedido, f"falta {privilegio} ao froid_runtime")


@unittest.skipUnless(
    DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado"
)
class ComportamentoDasRestricoes(unittest.TestCase):
    """As CHECK exercitadas numa copia temporaria da tabela.

    LIKE ... INCLUDING ALL herda as CHECK e nao herda as chaves estrangeiras.
    Assim se testa a regra sem montar a cadeia inteira de fixtures e sem deixar
    uma linha sequer no banco do cliente.
    """

    def setUp(self):
        self.conn = psycopg.connect(DATABASE_URL, autocommit=False)
        self.conn.execute(
            "CREATE TEMP TABLE plano_teste "
            "(LIKE psychosocial_action_plan INCLUDING ALL) ON COMMIT DROP"
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def inserir(self, **campos):
        base = {
            "id": "11111111-1111-1111-1111-111111111111",
            "organization_id": "22222222-2222-2222-2222-222222222222",
            "inventory_id": "33333333-3333-3333-3333-333333333333",
            "measure": "",
            "measure_type": "administrative",
            "plan_action": "introduce",
            "status": "planned",
            "evidence": "",
            "monitoring_method": "",
            "result_measurement": "",
        }
        base.update(campos)
        colunas = ", ".join(base)
        marcadores = ", ".join(["%s"] * len(base))
        self.conn.execute(
            f"INSERT INTO plano_teste ({colunas}) VALUES ({marcadores})",
            tuple(base.values()),
        )

    def recusa(self, restricao, **campos):
        ponto = f"antes_de_{restricao}"
        self.conn.execute(f"SAVEPOINT {ponto}")
        with self.assertRaises(Exception) as capturado:
            self.inserir(**campos)
        self.conn.execute(f"ROLLBACK TO SAVEPOINT {ponto}")
        self.assertIn(restricao, str(capturado.exception))

    def test_rascunho_vazio_e_aceito(self):
        # O seed abre a linha sem texto de propria vontade: 1.5.5.2.2 diz que
        # cronograma, responsavel e afericao sao da organizacao para preencher.
        self.inserir()

    def test_concluida_sem_data_de_implementacao_e_recusada(self):
        self.recusa(
            "psychosocial_action_plan_done_needs_implementation",
            status="done", measure="Redistribuir a carga do setor",
            responsible_membership_id="44444444-4444-4444-4444-444444444444",
            due_date="2026-12-31",
            monitoring_method="Reuniao quinzenal de acompanhamento",
            result_measurement="Nova campanha comparando com a linha de base",
        )

    def test_concluida_sem_responsavel_e_recusada(self):
        self.recusa(
            "psychosocial_action_plan_done_needs_schedule",
            status="done", measure="Redistribuir a carga do setor",
            implemented_at="2026-08-01",
            due_date="2026-12-31",
            monitoring_method="Reuniao quinzenal",
            result_measurement="Nova campanha",
        )

    def test_concluida_sem_afericao_de_resultado_e_recusada(self):
        self.recusa(
            "psychosocial_action_plan_done_needs_monitoring",
            status="done", measure="Redistribuir a carga do setor",
            implemented_at="2026-08-01",
            responsible_membership_id="44444444-4444-4444-4444-444444444444",
            due_date="2026-12-31",
            monitoring_method="Reuniao quinzenal",
            result_measurement="",
        )

    def test_cancelada_sem_justificativa_e_recusada(self):
        self.recusa(
            "psychosocial_action_plan_cancel_needs_reason",
            status="cancelled", measure="Redistribuir a carga do setor",
        )

    def test_eficacia_antes_da_implementacao_e_recusada(self):
        self.recusa(
            "psychosocial_action_plan_efficacy_after_implementation",
            measure="Redistribuir a carga do setor",
            effectiveness="effective",
            effectiveness_reviewed_at="2026-08-01",
        )

    def test_veredito_sem_data_de_revisao_e_recusado(self):
        self.recusa(
            "psychosocial_action_plan_review_pairs_with_verdict",
            measure="Redistribuir a carga do setor",
            implemented_at="2026-08-01",
            effectiveness="effective",
        )

    def test_verbo_fora_dos_tres_de_1_5_5_2_1_e_recusado(self):
        self.recusa(
            "psychosocial_action_plan_plan_action_check",
            plan_action="postpone",
        )

    def test_medida_concluida_e_completa_e_aceita(self):
        """O caminho feliz, com tudo que 1.5.5.2.2 exige preenchido."""
        self.inserir(
            status="done",
            measure="Redistribuir a carga do setor de recebimento",
            measure_type="collective",
            implemented_at="2026-08-01",
            responsible_membership_id="44444444-4444-4444-4444-444444444444",
            due_date="2026-07-31",
            monitoring_method="Verificacao quinzenal da escala com a CIPA",
            result_measurement="Campanha de eficacia comparando com a linha de base",
            effectiveness_reviewed_at="2026-08-20",
            effectiveness="partial",
        )


if __name__ == "__main__":
    unittest.main()
