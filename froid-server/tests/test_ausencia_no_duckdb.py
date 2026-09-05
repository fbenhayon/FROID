"""A ausencia sobrevive ao banco, e a consulta mostra o denominador.

Os testes irmaos (`test_ausencia_no_acervo`, `test_ausencia_utilitarios`,
`test_ausencia_na_leitura`) sao estaticos e puros, porque `duckdb` nao esta
instalado em toda maquina. Este exige o banco de verdade e e pulado sem ele —
mas quando roda, e o unico que prova a coisa inteira:

  1. `None` chega ao DuckDB como NULL, e nao como 0.0;
  2. `AVG()` ignora o NULL — que e correto e, sozinho, enganoso;
  3. `COUNT(<coluna>)` revela sobre quantas linhas a media foi calculada.

O (2) e o (3) sao a mesma frase: sem o N ao lado, uma coorte de 3 sessoes das
quais 2 nao mediram voz responde uma media de UMA sessao como se fosse da
coorte. Este arquivo trava exatamente esse par.

O ESQUEMA VEM DO `main.py`, PELO PARSER. Copia-lo aqui criaria um espelho de
esquema que divergiria em silencio na primeira coluna nova — o defeito que esta
casa ja pagou com pisos de coorte divergentes em quatro lugares.
"""

import ast
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None
MAIN_SRC = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
MAIN_TREE = ast.parse(MAIN_SRC)


def _create_statement(tabela: str) -> str:
    """O CREATE TABLE de verdade, tirado do `main.py` pelo parser."""
    marcador = f"CREATE TABLE IF NOT EXISTS {tabela}"
    for no in ast.walk(MAIN_TREE):
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and marcador in no.value:
            return no.value
    raise AssertionError(f"nao achei o CREATE de {tabela} em main.py")


@unittest.skipUnless(DUCKDB_AVAILABLE, "duckdb faz parte da imagem do backend")
class AusenciaSobreviveAoAcervo(unittest.TestCase):
    def setUp(self):
        import duckdb

        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.conn = duckdb.connect(str(Path(self.dir.name) / "acervo.duckdb"))
        self.addCleanup(self.conn.close)
        self.conn.execute(_create_statement("anonymous_session_cuts"))
        self.conn.execute(_create_statement("anonymous_sessions"))

    def _grava_corte(self, session_hash, ipm, jitter, f0):
        self.conn.execute(
            "INSERT INTO anonymous_session_cuts (session_hash, cut_index, ipm_avg, jitter, f0_mean) "
            "VALUES (?, ?, ?, ?, ?)",
            [session_hash, 0, ipm, jitter, f0],
        )

    def test_none_vira_null_e_nao_zero(self):
        """A causa raiz: era aqui que `_safe_float` punha 0.0."""
        self._grava_corte("sem_voz", None, None, None)
        linha = self.conn.execute(
            "SELECT ipm_avg, jitter, f0_mean FROM anonymous_session_cuts WHERE session_hash='sem_voz'"
        ).fetchone()
        self.assertEqual((None, None, None), linha)

    def test_zero_medido_continua_zero_no_banco(self):
        """A outra ponta da regra: nao trocar uma suposicao por outra.

        Um jitter medido de 0.0 e uma medida, e precisa continuar
        distinguivel de um jitter nao medido.
        """
        self._grava_corte("mediu_zero", 0.0, 0.0, 0.0)
        linha = self.conn.execute(
            "SELECT ipm_avg, jitter FROM anonymous_session_cuts WHERE session_hash='mediu_zero'"
        ).fetchone()
        self.assertEqual((0.0, 0.0), linha)
        self.assertIsNotNone(linha[0])

    def test_media_ignora_o_nao_apurado_e_o_count_denuncia_o_denominador(self):
        """O RISCO CENTRAL desta mudanca, travado.

        Tres sessoes, uma so com voz medida. `AVG` responde 60 — a media de UMA
        sessao. Sem `COUNT(ipm_avg)` ao lado, essa media sai anunciada como
        sendo das tres, e ninguem tem como perceber.
        """
        self._grava_corte("a", 60.0, 0.01, 180.0)
        self._grava_corte("b", None, None, None)
        self._grava_corte("c", None, None, None)
        media, n_medido, n_linhas = self.conn.execute(
            "SELECT AVG(ipm_avg), COUNT(ipm_avg), COUNT(*) FROM anonymous_session_cuts"
        ).fetchone()
        self.assertEqual(60.0, media)
        self.assertEqual(1, n_medido)
        self.assertEqual(3, n_linhas)
        self.assertNotEqual(n_medido, n_linhas, "o teste precisa de coorte parcial para valer")

    def test_o_zero_da_v3_teria_mentido_na_mesma_consulta(self):
        """Por que a v4 existe, demonstrado em vez de afirmado.

        As mesmas tres sessoes, gravadas como a v3 gravava: a media cai de 60
        para 20 e o `COUNT` nao acusa nada, porque as tres linhas tem numero.
        """
        self._grava_corte("a", 60.0, 0.01, 180.0)
        self._grava_corte("b", 0.0, 0.0, 0.0)
        self._grava_corte("c", 0.0, 0.0, 0.0)
        media, n_medido = self.conn.execute(
            "SELECT AVG(ipm_avg), COUNT(ipm_avg) FROM anonymous_session_cuts"
        ).fetchone()
        self.assertEqual(20.0, media)
        self.assertEqual(3, n_medido)

    def test_zona_nula_nao_vira_balde_zero(self):
        """`GROUP BY dominant_zone` tinha um balde "0" que era ausencia."""
        self.conn.execute(
            "INSERT INTO anonymous_sessions (session_hash, dominant_zone) VALUES (?, ?)",
            ["sem_zona", None],
        )
        self.conn.execute(
            "INSERT INTO anonymous_sessions (session_hash, dominant_zone) VALUES (?, ?)",
            ["zona_3", 3],
        )
        baldes = {
            linha[0]
            for linha in self.conn.execute(
                "SELECT dominant_zone FROM anonymous_sessions GROUP BY dominant_zone"
            ).fetchall()
        }
        self.assertIn(3, baldes)
        self.assertIn(None, baldes)
        self.assertNotIn(0, baldes)

    def test_as_duas_eras_do_acervo_sao_separaveis(self):
        """Sem `schema_version`, linhas com 0.0 e linhas com NULL entram no
        mesmo AVG e o resultado nao e de nenhuma das duas."""
        self.conn.execute(
            "INSERT INTO anonymous_sessions (session_hash, schema_version, ipm_score) VALUES (?, ?, ?)",
            ["antiga", "anonymous_datamart_v3", 0.0],
        )
        self.conn.execute(
            "INSERT INTO anonymous_sessions (session_hash, schema_version, ipm_score) VALUES (?, ?, ?)",
            ["nova", "anonymous_datamart_v4", None],
        )
        self.conn.execute(
            "INSERT INTO anonymous_sessions (session_hash, schema_version, ipm_score) VALUES (?, ?, ?)",
            ["nova_medida", "anonymous_datamart_v4", 55.0],
        )
        media_v4, n_v4 = self.conn.execute(
            "SELECT AVG(ipm_score), COUNT(ipm_score) FROM anonymous_sessions "
            "WHERE schema_version = 'anonymous_datamart_v4'"
        ).fetchone()
        self.assertEqual(55.0, media_v4)
        self.assertEqual(1, n_v4)
        media_tudo = self.conn.execute("SELECT AVG(ipm_score) FROM anonymous_sessions").fetchone()[0]
        self.assertEqual(27.5, media_tudo, "o zero da v3 contamina a media quando as eras se misturam")


if __name__ == "__main__":
    unittest.main()
