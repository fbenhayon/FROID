"""O ritmo da fala no FROID Explica: literatura como contexto, nunca como faixa.

Decisao do dono, 11/11/2026, depois da verificacao das fontes no texto dos
artigos: a tabela de cadencia de 09/11/2026 atribuia numeros a artigos que nao
os contem (97,8 PPM a Cohen 2014; "> 190" a um estudo que nao traz media) e
mandava encaixar a fala do paciente numa faixa. Os numeros dos estudos vem de
outras linguas, tarefas e formas de contar e nao sao comparaveis aos do FROID;
o paciente e comparado consigo mesmo. Estes testes guardam isso.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import explica_clinico  # noqa: E402


class ALiteraturaEContextoNaoFaixa(unittest.TestCase):
    def setUp(self):
        self.texto = explica_clinico._CADENCIA_LITERATURA

    def test_a_tabela_antiga_e_os_numeros_sem_fonte_nao_voltam(self):
        fonte = (SERVER_DIR / "explica_clinico.py").read_text(encoding="utf-8")
        self.assertNotIn("TABELA DE CADENCIA DA LITERATURA", fonte)
        for sem_fonte in ("97,8", "190 ou mais", "150 a 190", "Abaixo de 100:", "Abaixo de 50:"):
            self.assertNotIn(sem_fonte, self.texto)

    def test_declara_que_nao_e_regua_e_que_nao_e_comparavel(self):
        self.assertIn("NAO e regua", self.texto)
        self.assertIn("nao\ncomparavel", self.texto.replace("nao e\ncomparavel", "nao\ncomparavel"))
        self.assertIn("NUNCA como \"o\npaciente esta na faixa de\"", self.texto)

    def test_os_numeros_verificados_estao_com_a_fonte_certa(self):
        for trecho in (
            "96,0 (DP 44,8) x 134,9 (DP 40,2)",
            "Wiseman et al., Translational Psychiatry 2025",
            "Yuan, Liberman e Cieri, Interspeech 2006",
            "r = -0,378",
            "Eshghi et al.",
        ):
            self.assertIn(trecho, self.texto)

    def test_a_cadencia_e_so_da_fala_do_paciente_e_desta_sessao(self):
        indice = next(i for i in explica_clinico.CATALOGO if i.rotulo == "CADÊNCIA")
        self.assertIn("NA FALA DO PACIENTE", indice.medida)
        self.assertIn("nao o ESTADO em que ele", indice.leitura.replace("\n", " "))


if __name__ == "__main__":
    unittest.main()
