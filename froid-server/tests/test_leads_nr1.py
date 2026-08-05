"""Formulario publico na internet e alvo de robo antes de ser alvo de cliente."""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


class EndpointPublicoTests(unittest.TestCase):
    def setUp(self):
        self.fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        i = self.fonte.index("async def register_nr1_lead")
        self.trecho = self.fonte[i:i + 2600]

    def test_tem_limite_de_taxa_por_ip(self):
        self.assertIn("_rate_limit_guard", self.trecho)
        self.assertIn("_client_ip(request)", self.trecho)

    def test_exige_nome_email_e_empresa(self):
        self.assertIn("nome, e-mail e empresa", self.trecho)

    def test_nao_finge_sucesso_quando_nao_consegue_gravar(self):
        # Devolver 200 sem gravar perderia o lead em silencio, que e pior que
        # a falha visivel: ninguem investiga o que parece ter funcionado.
        self.assertIn("503", self.trecho)
        self.assertIn("LOGGER.exception", self.trecho)

    def test_limita_o_tamanho_de_cada_campo(self):
        self.assertIn("def _texto(", self.trecho)
        self.assertIn("[:limite]", self.trecho)


class TabelaDeLeadsTests(unittest.TestCase):
    def setUp(self):
        self.sql = (
            SERVER_DIR / "migrations" / "021_marketing_leads.sql"
        ).read_text(encoding="utf-8")

    def test_email_e_chave_unica_normalizada(self):
        # Quem volta ao site e recalcula atualiza a propria visita em vez de
        # virar duas pessoas na base.
        self.assertIn("UNIQUE INDEX", self.sql)
        self.assertIn("lower(btrim(email))", self.sql)

    def test_preve_oposicao_ao_tratamento(self):
        self.assertIn("opt_out_at", self.sql)

    def test_nao_guarda_nada_sensivel(self):
        # A tabela vive fora do RLS porque o lead ainda nao pertence a
        # organizacao nenhuma. Por isso mesmo nao pode receber dado sensivel.
        #
        # So as COLUNAS: o comentario da migration cita "resposta de
        # questionario" justamente para proibi-la, e checar o comentario faria
        # o teste reprovar o texto que existe para proteger.
        import re

        corpo = self.sql[
            self.sql.index("CREATE TABLE IF NOT EXISTS marketing_leads"):
            self.sql.index("CREATE UNIQUE INDEX")
        ]
        colunas = {
            m.group(1).lower()
            for m in re.finditer(r"^\s{4}([a-z_]+)\s+[A-Z]", corpo, re.M)
        }
        permitidas = {
            "id", "nome", "email", "empresa", "cargo", "contexto", "origem",
            "opt_out_at", "created_at",
        }
        self.assertEqual(colunas - permitidas, set(), f"coluna nova: {colunas}")

    def test_valida_email_e_nome_no_banco(self):
        self.assertIn("position('@' IN email)", self.sql)
        self.assertIn("length(btrim(nome))", self.sql)


class EsquemaSobDemandaTests(unittest.TestCase):
    """O endpoint publico precisa poder criar a propria tabela.

    As demais operacoes chegam ao tenant_store depois de autenticacao, que ja
    garantiu o esquema. Esta nao: num deploy novo, a tabela so existiria
    quando alguem da equipe logasse — e ate la o formulario devolveria 503 e
    perderia os leads em silencio, porque ninguem investiga um formulario que
    ninguem reclamou.
    """

    def test_register_marketing_lead_garante_o_esquema(self):
        fonte = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        i = fonte.index("def register_marketing_lead")
        corpo = fonte[i:fonte.index("INSERT INTO marketing_leads", i)]
        self.assertIn("self.ensure_schema()", corpo)


if __name__ == "__main__":
    unittest.main()
