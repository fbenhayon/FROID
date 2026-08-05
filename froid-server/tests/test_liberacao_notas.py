"""A lista de liberacao precisa cobrir o que a medicao de recuperacao exige.

Rodamos a reindexacao com um manifesto que negava por padrao — inclusive as
notas do FROID, que aguardavam uma revisao humana que nunca aconteceu. A base
ficou com 28 artigos de FACS e nenhuma nota propria, e o FROID Explica passou
a inventar: respondeu que IPM e "Indice de Performance Vocal" e IDM e "Indice
de Dissonancia Vocal". Nenhum dos dois existe.

Base incompleta mente com mais confianca que base vazia, porque o modelo
recupera algo parecido e completa o resto. Estes testes existem para que a
proxima reindexacao nao possa esvaziar a base em silencio.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def carregar(nome: str):
    caminho = SERVER_DIR / "tools" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class CoberturaDaMedicaoTests(unittest.TestCase):
    def setUp(self):
        self.liberacao = carregar("liberar_notas_froid")
        self.verificacao = carregar("verify_explica_retrieval")

    def test_toda_nota_esperada_pela_medicao_esta_liberada(self):
        # Se a medicao espera um documento que a lista nao libera, o acerto
        # cai para zero e ninguem sabe por que.
        esperados = {esperado for _, esperado in self.verificacao.CASOS}
        liberadas = set(self.liberacao.LIBERADAS)
        for esperado in esperados:
            achou = any(esperado.lower() in nome.lower() for nome in liberadas)
            self.assertTrue(
                achou,
                f"a medicao espera um documento contendo '{esperado}', e a "
                f"lista de liberacao nao tem nenhum",
            )

    def test_as_notas_liberadas_existem_no_repositorio(self):
        raiz = SERVER_DIR / "knowledge" / "approved"
        presentes = {p.name for p in raiz.rglob("*.md")}
        for nome in self.liberacao.LIBERADAS:
            if nome.startswith("FROID_Ficha") or nome.startswith("FROID_NR1") \
               or nome.startswith("FROID_Estabilizacao"):
                self.assertIn(nome, presentes, f"{nome} liberada mas ausente")

    def test_a_doutrina_fica_deliberadamente_fora(self):
        # Ela cita as frases proibidas para proibi-las; um corte de 150
        # palavras entregaria a frase sem a coluna que a nega.
        self.assertIn(
            "FROID_Fronteira_Medida_Interpretacao.md", self.liberacao.FORA
        )
        self.assertNotIn(
            "FROID_Fronteira_Medida_Interpretacao.md", self.liberacao.LIBERADAS
        )

    def test_cada_liberacao_tem_justificativa_escrita(self):
        for nome, motivo in self.liberacao.LIBERADAS.items():
            self.assertGreater(len(motivo.strip()), 20, nome)


class NotaDaEstabilizacaoTests(unittest.TestCase):
    """Ela so pode ser publica sem os pesos da janela."""

    def setUp(self):
        self.texto = (
            SERVER_DIR / "knowledge" / "approved" / "Notas_tecnicas_FROID"
            / "FROID_Estabilizacao_Clinica_Da_Tela.md"
        ).read_text(encoding="utf-8")

    def test_nao_publica_o_vetor_de_pesos(self):
        for peso in ("minuto -4: 10%", "minuto -3: 15%", "Pesos proprietarios"):
            self.assertNotIn(peso, self.texto)

    def test_mantem_o_racional_clinico(self):
        # O que o profissional precisa e a direcao do decaimento, nao o numero.
        self.assertIn("decai", self.texto)
        self.assertIn("cinco microjanelas", self.texto)

    def test_a_triagem_deixa_de_bloquear_por_implementacao(self):
        triagem = carregar("triagem_fontes_explica")
        achados = triagem.classificar(self.texto)["achados"]
        self.assertNotIn("implementacao_proprietaria", achados)


if __name__ == "__main__":
    unittest.main()
