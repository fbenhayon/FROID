"""A purga precisa recusar mais vezes do que aceita."""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


class PurgaTests(unittest.TestCase):
    def setUp(self):
        self.sql = (
            SERVER_DIR / "migrations" / "020_response_retention.sql"
        ).read_text(encoding="utf-8")

    def test_exige_campanha_encerrada(self):
        self.assertIn("coleta ainda aberta", self.sql)
        self.assertIn("c.closes_at < now() - make_interval", self.sql)

    def test_exige_inventario_consolidado(self):
        # Purgar antes de consolidar apagaria a unica evidencia de que a
        # avaliacao aconteceu — a empresa perderia a prova de conformidade
        # por excesso de zelo com o dado.
        self.assertIn("psychosocial_risk_inventory", self.sql)
        self.assertIn("inventario ainda nao consolidado", self.sql)

    def test_a_purga_recusa_em_vez_de_ignorar(self):
        # Omitir a campanha da lista faria o controle parecer funcionar
        # enquanto esconde o defeito. Ela levanta excecao com o motivo.
        self.assertIn("RAISE EXCEPTION", self.sql)
        self.assertIn("nao pode ser purgada", self.sql)

    def test_registra_o_que_foi_purgado(self):
        self.assertIn("responses_purged_at", self.sql)
        self.assertIn("responses_purged_count", self.sql)

    def test_nao_toca_no_inventario_nem_na_auditoria(self):
        # O unico DELETE do arquivo e o das respostas.
        deletes = [
            linha.strip() for linha in self.sql.splitlines()
            if "DELETE FROM" in linha.upper()
        ]
        self.assertEqual(len(deletes), 1, deletes)
        self.assertIn("assessment_responses", deletes[0])


class FerramentaTests(unittest.TestCase):
    def setUp(self):
        self.fonte = (SERVER_DIR / "tools" / "purgar_respostas.py").read_text(
            encoding="utf-8"
        )

    def test_dry_run_e_o_padrao(self):
        # Apagar dado sensivel precisa de um passo deliberado a mais que nao
        # apagar.
        self.assertIn('"--executar", action="store_true"', self.fonte)
        self.assertIn("if not args.executar:", self.fonte)
        self.assertIn("nada foi apagado", self.fonte)

    def test_mostra_o_motivo_de_cada_campanha_nao_elegivel(self):
        self.assertIn("motivo", self.fonte)
        self.assertIn("manter", self.fonte)


if __name__ == "__main__":
    unittest.main()
