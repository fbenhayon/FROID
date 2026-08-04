"""A nota que existe no repositorio precisa chegar ao FROID Explica.

Este arquivo nasce de um defeito silencioso. O ingestor escolhia UMA pasta:
o volume curado se existisse, senao o repositorio. Como em producao o volume
existe, toda nota tecnica versionada em git era descartada — sem erro, sem
aviso, sem aparecer em lugar nenhum. Escrevi uma nota sobre a NR-1, revisei,
publiquei, rodei a ingestao com saida de sucesso, e ela simplesmente nao
existia para o usuario.
"""

import importlib.util
from pathlib import Path
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
TOOL = SERVER_DIR / "tools" / "ingest_approved_sources.py"
APPROVED = SERVER_DIR / "knowledge" / "approved"


def load_tool():
    spec = importlib.util.spec_from_file_location("ingest_approved_sources", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()

    def test_repository_is_always_a_source(self):
        self.assertIn(self.tool.REPO_APPROVED_DIR, self.tool.default_sources())

    def test_repository_is_not_dropped_when_the_volume_exists(self):
        """O defeito original, travado.

        Não dá para simular o volume aqui sem escrever em /data, então a
        verificação é sobre a intenção do código: a seleção padrão precisa
        acumular as fontes, nunca escolher uma delas.
        """
        source = TOOL.read_text(encoding="utf-8")
        trecho = source[source.index("def default_sources"):]
        trecho = trecho[: trecho.index("\n\n\n") if "\n\n\n" in trecho else len(trecho)]
        self.assertIn("fontes.append(VOLUME_APPROVED_DIR)", trecho)
        self.assertNotIn("if VOLUME_APPROVED_DIR.exists() else REPO", trecho)

    def test_an_explicit_folder_still_wins(self):
        import os

        os.environ["FROID_APPROVED_KNOWLEDGE_DIR"] = str(APPROVED)
        try:
            self.assertEqual(self.tool.default_sources(), [APPROVED])
        finally:
            del os.environ["FROID_APPROVED_KNOWLEDGE_DIR"]

    def test_stable_id_derives_from_the_file_own_root(self):
        # Com mais de uma raiz, usar a raiz errada geraria identificadores
        # colidentes entre fontes diferentes.
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn("path.relative_to(raiz)", source)
        self.assertNotIn("path.relative_to(args.approved)", source)


class Nr1NoteTests(unittest.TestCase):
    """A nota do modulo NR-1 precisa existir e responder ao que promete."""

    @classmethod
    def setUpClass(cls):
        cls.path = APPROVED / "Notas_tecnicas_FROID" / "FROID_NR1_Riscos_Psicossociais.md"
        cls.text = cls.path.read_text(encoding="utf-8")

    def test_note_exists_and_is_indexable(self):
        self.assertTrue(self.path.exists())
        self.assertGreater(len(self.text), 3000)

    def test_declares_its_use_in_froid_explica(self):
        self.assertIn("Uso no FROID Explica:", self.text)
        self.assertIn("Area:", self.text)

    def test_answers_the_question_a_worker_will_actually_ask(self):
        # "Meu chefe vai ver o que eu respondi?" é a pergunta que decide a
        # adesão — e adesão baixa derruba o piso de coorte, que derruba o
        # inventário inteiro.
        self.assertIn("empregador nao le a sessao clinica", self.text.lower())
        self.assertIn("Para o empregador existe apenas o agregado", self.text)

    def test_explains_why_nothing_shows_during_collection(self):
        self.assertIn("enquanto a coleta esta aberta", self.text)
        self.assertIn("deduzir", self.text)

    def test_explains_why_the_system_refuses_to_claim_improvement(self):
        self.assertIn("intervalo alcanca o zero", self.text)

    def test_states_the_instrument_limit_instead_of_hiding_it(self):
        self.assertIn("nao possui validacao psicometrica publicada", self.text)

    def test_keeps_the_ascii_convention_of_the_other_notes(self):
        # As demais notas técnicas evitam acentuação; divergir aqui produziria
        # mojibake em qualquer pipeline que assuma latin-1.
        fora = sorted({c for c in self.text if ord(c) > 127})
        self.assertEqual(fora, [], f"caracteres nao-ascii: {fora}")


if __name__ == "__main__":
    unittest.main()
