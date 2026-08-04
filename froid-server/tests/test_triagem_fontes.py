"""A triagem nao pode confundir texto tecnico com segredo comercial.

Os dois falsos positivos abaixo apareceram na primeira execucao, contra a nota
tecnica da NR-1, e cada um bloquearia conteudo legitimo:

  * "margem de erro" — estatistica — casava com o padrao financeiro;
  * "1.5.4.4.5.3" — numeracao de subitem da norma — casava com o padrao de
    endereco IP.

Uma triagem que erra assim treina quem a usa a ignorar o alerta, e aí ela
deixa de proteger.
"""

import importlib.util
from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

TOOL = SERVER_DIR / "tools" / "triagem_fontes_explica.py"


def load():
    spec = importlib.util.spec_from_file_location("triagem_fontes_explica", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FalsoPositivoTests(unittest.TestCase):
    def setUp(self):
        self.tool = load()

    def categorias(self, texto: str) -> list[str]:
        return sorted(self.tool.classificar(texto)["achados"])

    def test_margem_de_erro_nao_e_financeiro(self):
        texto = (
            "O FROID calcula a diferenca padronizada e tambem a margem de erro "
            "dessa diferenca, que depende de quantas pessoas responderam."
        )
        self.assertNotIn("financeiro", self.categorias(texto))

    def test_margem_de_lucro_e_financeiro(self):
        self.assertIn(
            "financeiro", self.categorias("A margem de lucro projetada e de 62%.")
        )

    def test_numeracao_de_subitem_da_norma_nao_e_endereco(self):
        for subitem in ("1.5.4.4.4", "1.5.4.4.5.3", "1.5.7.3.2", "1.5.4.4.4.1"):
            texto = f"Conforme o subitem {subitem} da NR-1, a avaliacao considera."
            self.assertNotIn(
                "infra_interna", self.categorias(texto), f"subitem {subitem}"
            )

    def test_endereco_de_servidor_de_verdade_e_detectado(self):
        self.assertIn(
            "infra_interna",
            self.categorias("Conecte em 204.168.229.32 para publicar."),
        )

    def test_a_palavra_token_sozinha_nao_e_credencial(self):
        # O convite anonimo do NR-1 e explicado em termos de token de uso unico.
        texto = "O link do convite carrega um token de uso unico, que expira."
        self.assertNotIn("credencial", self.categorias(texto))

    def test_token_com_valor_atribuido_e_credencial(self):
        self.assertIn("credencial", self.categorias("token=abc123def456"))
        self.assertIn("credencial", self.categorias("senha: 12345678"))


class PosturaTests(unittest.TestCase):
    """Na duvida, nao indexa."""

    def setUp(self):
        self.tool = load()

    def test_documento_sem_sinal_nenhum_nao_e_liberado(self):
        indexar, motivo = self.tool.propor(
            "arquivo_qualquer.md", {"achados": {}, "sinais_literatura": 0}
        )
        self.assertFalse(indexar)
        self.assertIn("revisar", motivo)

    def test_documento_do_froid_exige_revisao_mesmo_sem_indicio(self):
        indexar, _ = self.tool.propor(
            "FROID_Nota_Tecnica.md", {"achados": {}, "sinais_literatura": 0}
        )
        self.assertFalse(indexar)

    def test_literatura_publicada_e_liberada(self):
        indexar, motivo = self.tool.propor(
            "fpsyt-16-1656292.pdf.md", {"achados": {}, "sinais_literatura": 5}
        )
        self.assertTrue(indexar)
        self.assertIn("literatura", motivo)

    def test_credencial_bloqueia_ainda_que_pareca_literatura(self):
        indexar, motivo = self.tool.propor(
            "paper.md", {"achados": {"credencial": ["x"]}, "sinais_literatura": 9}
        )
        self.assertFalse(indexar)
        self.assertIn("credencial", motivo)

    def test_financeiro_bloqueia_ainda_que_pareca_literatura(self):
        indexar, _ = self.tool.propor(
            "relatorio.md", {"achados": {"financeiro": ["x"]}, "sinais_literatura": 9}
        )
        self.assertFalse(indexar)


class ManifestoTests(unittest.TestCase):
    def test_ingestao_le_o_manifesto_e_nega_por_padrao(self):
        source = (SERVER_DIR / "tools" / "ingest_approved_sources.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("--manifesto", source)
        self.assertIn('item.get("indexar") is True', source)
        # Ausente do manifesto significa fora, e nao dentro.
        self.assertIn("path.name not in permitidos", source)


if __name__ == "__main__":
    unittest.main()
