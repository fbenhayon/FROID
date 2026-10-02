"""O piso de coorte do Data-FROID: um numero, uma regra, todas as copias iguais.

Decisao do Fabio em 02/10/2026: "bloqueia abaixo de 7".

Ate entao havia DUAS divergencias, e nenhuma aparecia em lugar nenhum:

- o servidor comparava com `<=`, entao o piso configurado em 50 exigia 51
  sessoes na pratica;
- o glossario do site, nos quatro idiomas, publicava "k >= 50" — e ainda
  descrevia o piso como garantia por REGISTRO ("indistinguivel de pelo menos
  outros 49"), quando o que o codigo faz e recusar CONSULTA a grupo pequeno.

Este teste amarra o numero e a regra a uma fonte so — o default de
`FROID_ANALYTICS_MIN_K` em `main.py` — e varre as copias por FORMA, nao por
arquivo: uma pagina nova que escreva "k >= N" entra na varredura sem ninguem
precisar lembrar dela.
"""

import ast
import re
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
MAIN = SERVER_DIR / "main.py"

# "k ≥ 7", "k >= 7", "(k ≥ 7)" — a forma em que o piso e AFIRMADO.
AFIRMACAO_DO_PISO = re.compile(r"\bk\s*(?:≥|>=|&ge;)\s*(\d+)")


def _arvore_main() -> ast.Module:
    return ast.parse(MAIN.read_text(encoding="utf-8"))


def _piso_da_fonte() -> int:
    """O default literal de FROID_ANALYTICS_MIN_K, lido pelo parser."""
    for no in ast.walk(_arvore_main()):
        if (
            isinstance(no, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "FROID_ANALYTICS_MIN_K" for t in no.targets)
        ):
            literais = [
                c.value
                for c in ast.walk(no.value)
                if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value.isdigit()
            ]
            assert literais, "FROID_ANALYTICS_MIN_K sem default literal"
            assert len(set(literais)) == 1, f"defaults divergentes na propria linha: {literais}"
            return int(literais[0])
    raise AssertionError("FROID_ANALYTICS_MIN_K nao encontrado em main.py")


class PisoDoDataFroidTest(unittest.TestCase):
    def test_o_piso_e_o_que_o_dono_decidiu(self):
        self.assertEqual(_piso_da_fonte(), 7)

    def test_toda_comparacao_com_o_piso_bloqueia_ABAIXO_dele(self):
        """N passa, N-1 nao. `<=` exigiria N+1 e desmentiria o numero escrito."""
        comparacoes = []
        for no in ast.walk(_arvore_main()):
            if not isinstance(no, ast.Compare):
                continue
            nomes = [no.left, *no.comparators]
            if any(isinstance(n, ast.Name) and n.id == "FROID_ANALYTICS_MIN_K" for n in nomes):
                comparacoes.append(no)
        self.assertTrue(comparacoes, "nenhuma comparacao com o piso — o portao sumiu?")
        for no in comparacoes:
            self.assertEqual(len(no.ops), 1)
            self.assertIsInstance(
                no.ops[0], ast.Lt,
                f"linha {no.lineno}: o portao tem de ser `cohort_size < FROID_ANALYTICS_MIN_K`",
            )
            self.assertIsInstance(no.left, ast.Name)
            self.assertEqual(no.left.id, "cohort_size")

    def test_compose_e_exemplos_de_ambiente_espelham_a_fonte(self):
        piso = _piso_da_fonte()
        compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn(f"FROID_ANALYTICS_MIN_K=${{FROID_ANALYTICS_MIN_K:-{piso}}}", compose)
        for exemplo in (REPO / ".env.example", SERVER_DIR / ".env.multitenant.example"):
            valores = re.findall(
                r"^FROID_ANALYTICS_MIN_K=(\d+)\s*$",
                exemplo.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            )
            self.assertEqual(valores, [str(piso)], exemplo.name)

    def test_toda_afirmacao_publica_do_piso_e_o_numero_da_fonte(self):
        piso = _piso_da_fonte()
        alvos = [
            *(REPO / "froid-site").rglob("*.html"),
            *(REPO / "froid-dashboard" / "src").rglob("*.ts*"),
            *(REPO / "froid-dashboard" / "src").rglob("*.html"),
        ]
        achados = []
        for caminho in alvos:
            texto = caminho.read_text(encoding="utf-8", errors="replace")
            for m in AFIRMACAO_DO_PISO.finditer(texto):
                achados.append((caminho.relative_to(REPO).as_posix(), int(m.group(1))))
        # Sem achado nenhum o teste passaria por vacuidade: os quatro glossarios
        # tem de ser encontrados, senao o padrao deixou de casar com a pagina.
        glossarios = [a for a in achados if a[0].endswith("glossario.html")]
        self.assertGreaterEqual(len(glossarios), 4, achados)
        divergentes = [a for a in achados if a[1] != piso]
        self.assertEqual(divergentes, [], f"piso publicado diferente de {piso}")

    def test_o_glossario_nao_promete_garantia_por_registro(self):
        """O codigo recusa CONSULTA a grupo pequeno; nao torna cada registro
        indistinguivel de outros N-1, nem torna a reidentificacao impossivel."""
        proibidas = ("outros 49", "49 others", "otros 49", "49 autres")
        for caminho in (REPO / "froid-site").rglob("glossario.html"):
            texto = caminho.read_text(encoding="utf-8")
            for frase in proibidas:
                self.assertNotIn(frase, texto, caminho.as_posix())


if __name__ == "__main__":
    unittest.main()
