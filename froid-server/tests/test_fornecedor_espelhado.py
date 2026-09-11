"""A identidade do FORNECEDOR tem uma fonte, e as copias nao podem divergir.

O CASO QUE ISTO EXISTE PARA IMPEDIR
-----------------------------------
Em 11/09/2026 o FORNECEDOR deixou de ser pessoa fisica e passou a ser a Froid
Digital Ltda. Duas coisas apareceram no mesmo dia:

1. A qualificacao da parte era montada com a palavra "CPF" ESCRITA NO CODIGO
   (`f"{name}, CPF {tax_id}, ..."`). Com uma Ltda, os SETE documentos do
   catalogo passariam a dizer "Froid Digital Ltda, CPF 05.215.763/0001-73" —
   afirmacao falsa sobre uma das partes, em todo documento assinado, e
   invisivel para quem nao conferir digito a digito.

2. O site nomeia a razao social e o CNPJ em OITO arquivos, quatro idiomas de
   `termos.html` e quatro de `proposta-nr1.html`. E o mesmo formato de defeito
   do piso de coorte que ficou publicado com o valor velho por semanas: nao
   quebra funcao nenhuma e se manifesta na frente do cliente.

O QUE ESTE TESTE PODE E O QUE NAO PODE
--------------------------------------
Nao da para comparar o site contra a fonte de verdade: do lado do produto a
identidade vive em `FROID_LEGAL_SUPPLIER_NAME` e `FROID_LEGAL_SUPPLIER_TAX_ID`,
no `.env` do servidor, que por decisao de projeto nao existe no Git. Entao o
teste trava o que da para travar — a divergencia ENTRE as copias — varrendo
`froid-site/**/*.html` inteiro, e nao a lista de arquivos que eu conhecia. Copia
nova numa pagina que ainda nao existe entra na varredura sozinha.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# A FONTE do lado do site. Mudou a empresa? Muda aqui, e o teste aponta cada
# copia que ficou para tras — inclusive nas traducoes, que sao onde se esquece.
RAZAO_SOCIAL = "Froid Digital Ltda"
CNPJ = "05.215.763/0001-73"

SITE = REPO / "froid-site"
CNPJ_QUALQUER = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")


def _paginas():
    return sorted(SITE.rglob("*.html"))


class OCnpjNaoDivergeEntreAsCopias(unittest.TestCase):
    def test_todo_cnpj_publicado_e_o_mesmo(self):
        achados = {}
        for pagina in _paginas():
            texto = pagina.read_text(encoding="utf-8")
            for encontrado in CNPJ_QUALQUER.findall(texto):
                achados.setdefault(encontrado, []).append(
                    str(pagina.relative_to(REPO))
                )
        # Zero ocorrencia tambem e defeito: significa que o site deixou de
        # identificar a parte contratante, e um teste que passa com o site vazio
        # nao esta defendendo nada.
        self.assertTrue(achados, "nenhum CNPJ publicado no site")
        self.assertEqual(
            sorted(achados),
            [CNPJ],
            f"CNPJ divergente publicado: { {k: v for k, v in achados.items() if k != CNPJ} }",
        )

    def test_a_razao_social_acompanha_o_cnpj(self):
        """Numero certo com nome errado identifica a parte errada do mesmo jeito."""
        for pagina in _paginas():
            texto = pagina.read_text(encoding="utf-8")
            if CNPJ not in texto:
                continue
            with self.subTest(pagina=str(pagina.relative_to(REPO))):
                self.assertIn(RAZAO_SOCIAL, texto)

    def test_o_titular_anterior_nao_ficou_para_tras(self):
        """A pessoa fisica nao pode mais aparecer como titular nem como parte.

        `sobre-contato.html` e a excecao declarada: ali o nome aparece na
        biografia de quem fundou o FROID, que continua sendo verdade.
        """
        for pagina in _paginas():
            if pagina.name == "sobre-contato.html":
                continue
            texto = pagina.read_text(encoding="utf-8")
            with self.subTest(pagina=str(pagina.relative_to(REPO))):
                for frase in (
                    "Benhayon é o autor e titular",
                    "Benhayon is the author and rights holder",
                    "Benhayon es el autor y titular",
                    "Benhayon est l'auteur et le titulaire",
                    "FROID — Fábio de Assumpção Benhayon",
                ):
                    self.assertNotIn(frase, texto)


class ORotuloDoDocumentoNaoEstaNoCodigo(unittest.TestCase):
    """"CPF" literal na qualificacao da parte foi o defeito central da troca."""

    def setUp(self):
        self.legal = (SERVER_DIR / "legal_documents.py").read_text(encoding="utf-8")

    def test_a_identidade_usa_o_rotulo_derivado(self):
        self.assertIn("{supplier['tax_id_label']}", self.legal)
        # A regra varre o ARQUIVO, e nao a ocorrencia que eu vi.
        self.assertNotIn("CPF {supplier", self.legal)
        self.assertNotIn("CNPJ {supplier", self.legal)

    def test_o_rotulo_vem_do_documento_e_recusa_o_que_nao_reconhece(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "legal_documents_fornecedor", SERVER_DIR / "legal_documents.py"
        )
        modulo = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(modulo)
        self.assertEqual(modulo._tax_id_label(CNPJ), "CNPJ")
        self.assertEqual(modulo._tax_id_label("050.983.408-61"), "CPF")
        for desconhecido in ("", "123", "ES-B12345678", "abc"):
            with self.subTest(documento=desconhecido):
                self.assertEqual(modulo._tax_id_label(desconhecido), "")

    def test_a_versao_declara_a_natureza_juridica(self):
        """O sufixo `br-pf` significava pessoa fisica, e virou mentira."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "legal_documents_versao", SERVER_DIR / "legal_documents.py"
        )
        modulo = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(modulo)
        self.assertIn("br-pj", modulo.LEGAL_DOCUMENT_VERSION)
        self.assertNotIn("br-pf", modulo.LEGAL_DOCUMENT_VERSION)


if __name__ == "__main__":
    unittest.main()
