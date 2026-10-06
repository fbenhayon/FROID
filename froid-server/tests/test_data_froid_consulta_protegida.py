"""A consulta ao Data-FROID pelo FROID Explica: o que a auditoria de 05/10/2026 fechou.

O caminho e: pergunta do profissional -> modelo escreve SQL -> DuckDB -> modelo
narra o resultado. Ate aqui, as guardas eram de FORMA (so SELECT, sem DDL, so
as duas tabelas) e um piso de coorte calculado por uma SEGUNDA consulta,
tambem escrita pelo modelo. Tres brechas, que ficaram graves quando o tema
passou a ser texto livre (Fase 1):

1. nada exigia agregacao — `SELECT theme_predominant FROM anonymous_session_cuts
   LIMIT 50` passava por todas as guardas e devolvia linhas individuais;
2. `SELECT *` devolvia toda coluna sem escrever o nome de nenhuma;
3. o piso rodava na consulta de coorte, nao na de resultado: `GROUP BY
   theme_predominant` com grupos de UMA sessao passava inteiro se a coorte
   total tivesse 7.

A saida: o SQL e lido pelo PROPRIO DuckDB (`json_serialize_sql`), que barra `*`,
UNION e coluna vedada em qualquer nivel; e o SELECT de topo tem de trazer
`COUNT(DISTINCT session_hash)`, que vira o piso POR LINHA — linha com menos de
7 sessoes distintas some inteira, e a quantidade suprimida e declarada.
"""

import ast
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None
MAIN_SRC = (SERVER_DIR / "main.py").read_text(encoding="utf-8")


def _fonte_da_funcao(nome: str) -> str:
    for no in ast.parse(MAIN_SRC).body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return ast.get_source_segment(MAIN_SRC, no) or ""
    raise AssertionError(f"nao achei {nome}")


SQL_OK = (
    "SELECT theme_predominant, COUNT(DISTINCT session_hash) AS sessoes, "
    "AVG(ipm_avg) AS ipm_medio, COUNT(ipm_avg) AS n_ipm "
    "FROM anonymous_session_cuts GROUP BY theme_predominant"
)


@unittest.skipUnless(DUCKDB_AVAILABLE, "duckdb e instalado na imagem do backend")
class OSQLELidoPeloProprioDuckDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import duckdb
        import main

        cls.main = main
        cls.conn = duckdb.connect()
        cls.conn.execute(
            "CREATE TABLE anonymous_sessions(session_hash VARCHAR, age_bucket VARCHAR, "
            "ipm_score DOUBLE, schema_version VARCHAR)"
        )
        cls.conn.execute(
            "CREATE TABLE anonymous_session_cuts(session_hash VARCHAR, theme_predominant VARCHAR, "
            "ipm_avg DOUBLE, professional_summary_anon VARCHAR, cut_context_json VARCHAR)"
        )
        # Tema 'x' em sete sessoes distintas; tema 'y' em uma so.
        for i in range(7):
            cls.conn.execute(
                "INSERT INTO anonymous_session_cuts VALUES (?, 'x', ?, 'fala do profissional', '{}')",
                [f"s{i}", 10.0 + i],
            )
        cls.conn.execute("INSERT INTO anonymous_session_cuts VALUES ('s9', 'y', 50.0, 'segredo', '{}')")

    def _bloqueia(self, sql, trecho):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            self.main._validate_duckdb_select(sql, self.conn)
        self.assertEqual(400, ctx.exception.status_code)
        self.assertIn(trecho, str(ctx.exception.detail))

    def test_consulta_agregada_passa(self):
        self.assertEqual(SQL_OK, self.main._validate_duckdb_select(SQL_OK, self.conn))

    def test_with_passa(self):
        sql = "WITH c AS (SELECT * FROM anonymous_session_cuts) SELECT 1"
        # `*` dentro da CTE e barrado tambem — qualquer nivel.
        self._bloqueia(sql, "SELECT *")
        sql = (
            "WITH c AS (SELECT session_hash, ipm_avg FROM anonymous_session_cuts) "
            "SELECT COUNT(DISTINCT session_hash) AS sessoes, AVG(ipm_avg) AS m FROM c"
        )
        self.assertEqual(sql, self.main._validate_duckdb_select(sql, self.conn))

    def test_estrela_e_barrada_em_qualquer_forma(self):
        self._bloqueia("SELECT * FROM anonymous_session_cuts", "SELECT *")
        self._bloqueia("SELECT c.* FROM anonymous_session_cuts c", "SELECT *")
        self._bloqueia(
            "SELECT COUNT(DISTINCT session_hash) AS sessoes FROM (SELECT * FROM anonymous_session_cuts) q",
            "SELECT *",
        )

    def test_union_e_barrado(self):
        self._bloqueia(
            "SELECT theme_predominant FROM anonymous_session_cuts UNION ALL SELECT age_bucket FROM anonymous_sessions",
            "UNION",
        )

    def test_coluna_vedada_e_barrada_em_qualquer_nivel(self):
        self._bloqueia(
            "SELECT professional_summary_anon, COUNT(DISTINCT session_hash) AS sessoes "
            "FROM anonymous_session_cuts GROUP BY 1",
            "professional_summary_anon",
        )
        # Por subconsulta, com outro apelido: a arvore ve a referencia original.
        self._bloqueia(
            "SELECT x, COUNT(DISTINCT session_hash) AS sessoes FROM "
            "(SELECT session_hash, professional_summary_anon AS x FROM anonymous_session_cuts) q GROUP BY 1",
            "professional_summary_anon",
        )
        self._bloqueia(
            "SELECT COUNT(DISTINCT session_hash) AS sessoes FROM anonymous_session_cuts "
            "WHERE cut_context_json LIKE '%a%'",
            "cut_context_json",
        )

    def test_as_guardas_de_forma_continuam(self):
        self._bloqueia("DELETE FROM anonymous_sessions", "apenas SELECT")
        self._bloqueia("SELECT 1; SELECT 2", "multiplas")
        self._bloqueia("SELECT COUNT(*) FROM outra_tabela", "anonymous_sessions")

    def test_sintaxe_invalida_e_recusada_com_motivo(self):
        self._bloqueia("SELEC x FROM anonymous_sessions", "SQL bloqueado")

    def test_sem_conexao_valem_so_as_regras_de_forma(self):
        """Compatibilidade: quem chama sem `conn` recebe o comportamento antigo."""
        self.assertEqual(
            "SELECT * FROM anonymous_sessions",
            self.main._validate_duckdb_select("SELECT * FROM anonymous_sessions"),
        )


@unittest.skipUnless(DUCKDB_AVAILABLE, "duckdb e instalado na imagem do backend")
class OPisoEPorLinha(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import duckdb
        import main

        cls.main = main
        cls.conn = duckdb.connect()
        cls.conn.execute("CREATE TABLE anonymous_session_cuts(session_hash VARCHAR, theme_predominant VARCHAR, ipm_avg DOUBLE)")
        for i in range(7):
            cls.conn.execute("INSERT INTO anonymous_session_cuts VALUES (?, 'x', ?)", [f"s{i}", 10.0 + i])
        cls.conn.execute("INSERT INTO anonymous_session_cuts VALUES ('s9', 'y', 50.0)")

    def _executa(self, sql):
        resultado = self.conn.execute(sql)
        colunas = [d[0] for d in resultado.description]
        return colunas, resultado.fetchall()

    def test_acha_a_coluna_de_sessoes_pelo_apelido(self):
        colunas, _ = self._executa(SQL_OK)
        self.assertEqual(1, self.main._coluna_de_sessoes(self.conn, SQL_OK, colunas))

    def test_acha_a_coluna_de_sessoes_sem_apelido_e_com_prefixo_de_tabela(self):
        sql = "SELECT AVG(c.ipm_avg), COUNT(DISTINCT c.session_hash) FROM anonymous_session_cuts c"
        colunas, _ = self._executa(sql)
        self.assertEqual(1, self.main._coluna_de_sessoes(self.conn, sql, colunas))

    def test_sem_a_contagem_a_consulta_e_recusada(self):
        from fastapi import HTTPException

        for sql in (
            "SELECT theme_predominant, AVG(ipm_avg) FROM anonymous_session_cuts GROUP BY 1",
            # COUNT sem DISTINCT conta cortes, nao sessoes.
            "SELECT theme_predominant, COUNT(session_hash) AS sessoes FROM anonymous_session_cuts GROUP BY 1",
            # A contagem dentro da CTE nao protege o SELECT de topo.
            "WITH t AS (SELECT theme_predominant, COUNT(DISTINCT session_hash) AS sessoes "
            "FROM anonymous_session_cuts GROUP BY 1) SELECT theme_predominant, sessoes FROM t",
        ):
            with self.subTest(sql=sql):
                colunas, _ = self._executa(sql)
                with self.assertRaises(HTTPException) as ctx:
                    self.main._coluna_de_sessoes(self.conn, sql, colunas)
                self.assertIn("COUNT(DISTINCT session_hash)", str(ctx.exception.detail))

    def test_linha_abaixo_do_piso_some_inteira_e_e_contada(self):
        colunas, linhas = self._executa(SQL_OK)
        indice = self.main._coluna_de_sessoes(self.conn, SQL_OK, colunas)
        mantidas, suprimidas = self.main._suprimir_abaixo_do_piso(linhas, indice, 7)
        self.assertEqual(1, suprimidas)
        self.assertEqual(1, len(mantidas))
        self.assertEqual("x", mantidas[0][0])
        # O tema 'y', de UMA sessao, nao aparece em lugar nenhum do que sobrou.
        self.assertNotIn("y", json.dumps(mantidas, default=str))

    def test_sete_passa_seis_nao(self):
        linhas = [("a", 7), ("b", 6), ("c", None)]
        mantidas, suprimidas = self.main._suprimir_abaixo_do_piso(linhas, 1, 7)
        self.assertEqual([("a", 7)], mantidas)
        self.assertEqual(2, suprimidas)


class AInstrucaoAoModeloEAsConsultasDeQuedaAcompanham(unittest.TestCase):
    def test_a_instrucao_exige_a_contagem_e_proibe_a_estrela(self):
        fonte = _fonte_da_funcao("_query_froid_analytics")
        self.assertIn("COUNT(DISTINCT session_hash) AS sessoes", fonte)
        self.assertIn("Nao use SELECT *", fonte)
        self.assertIn("transcript_scope", fonte)
        self.assertIn("theme_deid_reason", fonte)

    def test_toda_consulta_de_queda_traz_a_contagem_de_sessoes(self):
        fonte = _fonte_da_funcao("_fallback_analytics_sql")
        self.assertNotIn("COUNT(*) AS sessoes", fonte)
        self.assertGreaterEqual(fonte.count("COUNT(DISTINCT session_hash) AS sessoes"), 4)

    def test_o_resultado_passa_pelo_piso_por_linha(self):
        fonte = _fonte_da_funcao("_query_froid_analytics")
        self.assertIn("_coluna_de_sessoes(conn, result_sql, columns)", fonte)
        self.assertIn("_suprimir_abaixo_do_piso(rows, indice_sessoes, FROID_ANALYTICS_MIN_K)", fonte)
        self.assertIn("linha(s) suprimida(s)", fonte)


@unittest.skipUnless(DUCKDB_AVAILABLE, "duckdb e instalado na imagem do backend")
class AAuditoriaDoAcervoOlhaOTema(unittest.TestCase):
    """`tools/audit_data_froid_privacy.py` reprovava texto literal nas colunas de
    fala e nao olhava o tema — que agora e texto. Sinal de identificador
    (digito, arroba, endereco) no tema e reprovacao."""

    def _banco(self, path: Path, *, tema: str) -> None:
        import duckdb

        c = duckdb.connect(str(path))
        c.execute(
            "CREATE TABLE anonymous_sessions(session_hash VARCHAR, pii_excluded BOOLEAN, "
            "raw_audio_retained BOOLEAN, literal_transcript_retained BOOLEAN, ingestion_basis VARCHAR, "
            "summary_theme VARCHAR)"
        )
        c.execute(
            "CREATE TABLE anonymous_session_cuts(cut_summary_anon VARCHAR, patient_summary_anon VARCHAR, "
            "professional_summary_anon VARCHAR, relevant_dissonances VARCHAR, theme VARCHAR, theme_predominant VARCHAR)"
        )
        c.execute(
            "CREATE TABLE privacy_ingestion_audit(session_hash VARCHAR, accepted BOOLEAN, reason VARCHAR, "
            "checked_at VARCHAR, pipeline_version VARCHAR)"
        )
        c.execute(
            "INSERT INTO anonymous_sessions VALUES (?, true, false, false, 'post_anonymization', 'Luto e [NOME]')",
            ["a" * 64],
        )
        c.execute("INSERT INTO anonymous_session_cuts VALUES ('', '', '', '', ?, ?)", [tema, tema])
        c.execute("INSERT INTO privacy_ingestion_audit VALUES (?, true, 'approved', 'now', 'v3')", ["a" * 64])
        c.close()

    def _audita(self, path: Path):
        from tools import audit_data_froid_privacy

        saida = io.StringIO()
        with patch.object(sys, "argv", ["audit", "--database", str(path)]):
            with contextlib.redirect_stdout(saida):
                codigo = audit_data_froid_privacy.main()
        return codigo, json.loads(saida.getvalue())

    def test_tema_limpo_passa(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "ok.duckdb"
            self._banco(caminho, tema="Conflito com [NOME] no trabalho")
            codigo, resultado = self._audita(caminho)
            self.assertEqual(0, codigo, resultado)
            self.assertTrue(resultado["checks"]["theme_identifier_absent"])

    def test_tema_com_identificador_reprova(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "ruim.duckdb"
            self._banco(caminho, tema="Consulta dia 12/05 com joao@x.com")
            codigo, resultado = self._audita(caminho)
            self.assertEqual(1, codigo)
            self.assertEqual("failed", resultado["status"])
            self.assertFalse(resultado["checks"]["theme_identifier_absent"])


if __name__ == "__main__":
    unittest.main()
