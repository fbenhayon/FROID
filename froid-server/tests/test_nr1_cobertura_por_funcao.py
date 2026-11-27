"""Leitura de Governança: o grupo por função e os estabelecimentos que ele cobre.

26/11/2026. A liderança das lojas passa a poder ser avaliada por FUNÇÃO
("Gerentes de loja" atravessando as 40 lojas). O PGR continua sendo por
estabelecimento (NR-1 1.5.3.1.1.1), e o inventário descobria o estabelecimento
de cada linha pela unidade pai do recorte. Um grupo por função não tem pai: a
linha saía sem dizer ONDE está o risco. A migration 059 cria a cobertura, e a
listagem do inventário e do plano passa a dizer em quais endereços cada linha
vale.

Três camadas:
  1. o texto da migration declara o que precisa declarar;
  2. a listagem usa a cobertura nos dois documentos e projeta sem recalcular;
  3. contra um Postgres de verdade (pulado sem FROID_TEST_DATABASE_URL): a
     trava de tipos e o fragmento SQL da listagem sobre o schema real, dentro
     de uma transação desfeita no fim.
"""

import os
import sys
import unittest
import uuid
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MIGRACAO = (SERVER_DIR / "migrations" / "059_nr1_cobertura_por_funcao.sql").read_text(
    encoding="utf-8"
)
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

DATABASE_URL = os.getenv("FROID_TEST_DATABASE_URL", "")
try:  # pragma: no cover - import guard
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


class AMigracaoDeclaraACobertura(unittest.TestCase):
    def test_grupo_e_endereco_sao_da_mesma_empresa(self):
        # Chave composta com a organização: sem ela um grupo poderia cobrir o
        # estabelecimento de outra empresa.
        self.assertIn(
            "FOREIGN KEY (organization_id, unit_id)\n"
            "        REFERENCES organization_units (organization_id, id)",
            MIGRACAO,
        )
        self.assertIn(
            "FOREIGN KEY (organization_id, establishment_unit_id)\n"
            "        REFERENCES organization_units (organization_id, id)",
            MIGRACAO,
        )

    def test_so_grupo_por_funcao_cobre_e_so_estabelecimento_e_coberto(self):
        self.assertIn("IS DISTINCT FROM 'exposure_group'", MIGRACAO)
        self.assertIn("IS DISTINCT FROM 'site'", MIGRACAO)
        self.assertIn("BEFORE INSERT OR UPDATE ON organization_unit_coverage", MIGRACAO)

    def test_efetivo_por_endereco_e_positivo(self):
        self.assertIn("headcount integer NOT NULL CHECK (headcount > 0)", MIGRACAO)

    def test_rls_politicas_e_grant(self):
        self.assertIn(
            "ALTER TABLE organization_unit_coverage ENABLE ROW LEVEL SECURITY", MIGRACAO
        )
        self.assertIn("CREATE POLICY organization_unit_coverage_read", MIGRACAO)
        self.assertIn("CREATE POLICY organization_unit_coverage_manage", MIGRACAO)
        self.assertIn(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON organization_unit_coverage", MIGRACAO
        )

    def test_registra_a_versao(self):
        self.assertIn("VALUES ('059_nr1_cobertura_por_funcao')", MIGRACAO)


class AListagemDizOnde(unittest.TestCase):
    def _metodo(self, nome, fim):
        corpo = STORE[STORE.index(f"def {nome}("):]
        return corpo[: corpo.index(fim)]

    def test_inventario_e_plano_usam_a_mesma_regra(self):
        inventario = self._metodo("nr1_list_inventory", "def _nr1_inventory_row(")
        plano = self._metodo("nr1_list_action_plan", "def nr1_update_action_plan_item(")
        for corpo in (inventario, plano):
            self.assertIn("_NR1_ESTABELECIMENTOS_SQL", corpo)
            self.assertIn("unit.unit_type", corpo)
        self.assertIn('"establishments": _estabelecimentos(row[17])', STORE)
        self.assertIn('"establishments": _estabelecimentos(row[30])', STORE)

    def test_filtro_por_estabelecimento_inclui_setores_e_grupos_que_o_cobrem(self):
        inventario = self._metodo("nr1_list_inventory", "def _nr1_inventory_row(")
        self.assertIn("unit.parent_unit_id = %s::uuid", inventario)
        self.assertIn("cobertura.establishment_unit_id = %s::uuid", inventario)

    def test_o_fragmento_le_a_cobertura_e_o_pai(self):
        import tenant_store

        sql = tenant_store._NR1_ESTABELECIMENTOS_SQL
        self.assertIn("FROM organization_unit_coverage cobertura", sql)
        self.assertIn("WHEN unit.unit_type = 'exposure_group'", sql)
        self.assertIn("WHEN estabelecimento.id IS NOT NULL", sql)

    def test_json_em_texto_ou_decodificado_vira_a_mesma_lista(self):
        import tenant_store

        endereco = str(uuid.uuid4())
        bruto = [{"id": endereco, "name": "Loja 17", "headcount": 1}]
        self.assertEqual(
            tenant_store._estabelecimentos(bruto),
            tenant_store._estabelecimentos(
                '[{"id": "%s", "name": "Loja 17", "headcount": 1}]' % endereco
            ),
        )
        self.assertEqual(tenant_store._estabelecimentos(None), [])

    def test_projecao_copia_o_nivel_e_troca_so_o_onde(self):
        """Recalcular por loja seria publicar a resposta de uma pessoa."""
        import tenant_store

        loja = str(uuid.uuid4())
        linha = {
            "risk_level": "critical", "severity": 4, "probability": 5,
            "mean_score": 4.2, "cohort_size": 40, "site_name": None,
            "establishments": [
                {"id": loja, "name": "Loja 17", "headcount": 1},
                {"id": str(uuid.uuid4()), "name": "Loja 18", "headcount": 1},
            ],
        }
        projetada = tenant_store._projetar_no_estabelecimento(linha, loja)
        for campo in ("risk_level", "severity", "probability", "mean_score", "cohort_size"):
            self.assertEqual(projetada[campo], linha[campo])
        self.assertEqual(projetada["site_name"], "Loja 17")
        self.assertEqual(projetada["establishment_headcount"], 1)
        # A linha original não é alterada: a mesma lista serve às 40 lojas.
        self.assertIsNone(linha["site_name"])

    def test_endpoint_aceita_o_estabelecimento_e_recusa_id_malformado(self):
        trecho = MAIN[MAIN.index("async def list_nr1_inventory("):]
        trecho = trecho[: trecho.index("declaracao_da_campanha")]
        self.assertIn("establishment_id: Optional[str] = None", trecho)
        self.assertIn('status_code=400, detail="estabelecimento inválido"', trecho)
        self.assertIn("establishment_id=establishment_id", trecho)


@unittest.skipUnless(DATABASE_URL and psycopg, "FROID_TEST_DATABASE_URL nao configurado")
class ACoberturaContraOPostgres(unittest.TestCase):
    """Tudo dentro de uma transação desfeita: nenhuma linha fica no banco."""

    def setUp(self):
        self.conn = psycopg.connect(DATABASE_URL)
        self.org = str(uuid.uuid4())
        self.loja = str(uuid.uuid4())
        self.setor = str(uuid.uuid4())
        self.gerentes = str(uuid.uuid4())
        c = self.conn
        c.execute(
            "INSERT INTO organizations (id, organization_type, legal_name, display_name, status)"
            " VALUES (%s,'enterprise','Teste cobertura','Teste cobertura','active')",
            (self.org,),
        )
        c.execute(
            "INSERT INTO organization_units (id, organization_id, unit_type, name, headcount)"
            " VALUES (%s,%s,'site','Loja 17',8)",
            (self.loja, self.org),
        )
        c.execute(
            "INSERT INTO organization_units"
            " (id, organization_id, parent_unit_id, unit_type, name, headcount)"
            " VALUES (%s,%s,%s,'sector','Caixa',6)",
            (self.setor, self.org, self.loja),
        )
        c.execute(
            "INSERT INTO organization_units (id, organization_id, unit_type, name, headcount)"
            " VALUES (%s,%s,'exposure_group','Gerentes de loja',40)",
            (self.gerentes, self.org),
        )

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def _cobrir(self, unidade, endereco, pessoas=1):
        self.conn.execute(
            "INSERT INTO organization_unit_coverage"
            " (organization_id, unit_id, establishment_unit_id, headcount)"
            " VALUES (%s,%s,%s,%s)",
            (self.org, unidade, endereco, pessoas),
        )

    def test_grupo_cobre_estabelecimento(self):
        self._cobrir(self.gerentes, self.loja)

    def test_setor_nao_pode_ser_coberto_nem_cobrir(self):
        with self.assertRaises(psycopg.errors.RaiseException):
            self._cobrir(self.gerentes, self.setor)

    def test_setor_nao_pode_ser_grupo_de_cobertura(self):
        with self.assertRaises(psycopg.errors.RaiseException):
            self._cobrir(self.setor, self.loja)

    def _onde(self, unidade):
        import tenant_store

        return tenant_store._estabelecimentos(self.conn.execute(
            "SELECT " + tenant_store._NR1_ESTABELECIMENTOS_SQL + """
              FROM (SELECT %s::uuid AS unit_id, %s::uuid AS organization_id) inventory
              JOIN organization_units unit ON unit.id = inventory.unit_id
              LEFT JOIN organization_units estabelecimento
                ON estabelecimento.id = unit.parent_unit_id
            """,
            (unidade, self.org),
        ).fetchone()[0])

    def test_o_fragmento_da_listagem_sobre_o_schema_real(self):
        self.assertEqual(self._onde(self.gerentes), [])
        self._cobrir(self.gerentes, self.loja)
        self.assertEqual(
            self._onde(self.gerentes),
            [{"id": self.loja, "name": "Loja 17", "headcount": 1}],
        )
        self.assertEqual(
            self._onde(self.setor),
            [{"id": self.loja, "name": "Loja 17", "headcount": 6}],
        )


if __name__ == "__main__":
    unittest.main()
