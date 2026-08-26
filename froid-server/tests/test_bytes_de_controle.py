"""Byte de controle no fonte transforma verificador em enfeite.

Encontrado em 26/08/2026, durante a apuracao da consulta perdida.

`tests/test_runtime_grants.py` tinha, desde 05/08, um byte 0x08 (backspace) no
lugar da ancora `\\b` de uma f-string de regex:

    rf"(INSERT INTO|UPDATE)\\s+{tabela}<0x08>"

Backspace nao aparece no codigo-fonte que ele varre. A regex nunca casava nada,
o laco nunca entrava, e o teste passava — verde, rapido e inutil. Ele existia
para impedir que quatro tabelas escritas pelo owner passassem a ser escritas
pelo papel de runtime (webhook de pagamento, contabilidade de migracao e o
livro imutavel de aceites legais). Por tres semanas nao impediu nada.

Foi reparado, e ao rodar de verdade passou — nao havia violacao escondida. Mas
o intervalo entre "escrevi a trava" e "a trava funciona" foi de tres semanas,
e ninguem tinha como saber.

POR QUE ISTO MERECE VARREDURA PROPRIA

O defeito e invisivel por construcao: o byte nao se ve no editor, o arquivo e
UTF-8 valido, o Python parseia, o teste passa. Nada acusa. E o mesmo formato de
falha do `peer-waiting` sem leitor e do espelho de piso que sobreviveu a uma
migration — coisas que nao dao erro, so deixam de fazer o que prometiam.

A varredura e barata: um byte C0 fora de tab, LF e CR nao tem uso legitimo em
codigo-fonte deste repositorio.
"""

import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent

# Tab, LF e CR sao os unicos controles legitimos em fonte.
PERMITIDOS = {0x09, 0x0A, 0x0D}

RAIZES = (
    (REPO / "froid-server", ("*.py", "*.sql")),
    (REPO / "froid-dashboard" / "src", ("*.ts", "*.tsx", "*.css")),
    (REPO / "froid-site", ("*.html",)),
)

IGNORADOS = ("node_modules", "venv", ".venv", "__pycache__", "dist", "build")


def _arquivos():
    for raiz, padroes in RAIZES:
        if not raiz.exists():
            continue
        for padrao in padroes:
            for caminho in raiz.rglob(padrao):
                if any(parte in IGNORADOS for parte in caminho.parts):
                    continue
                yield caminho


class NenhumByteDeControleNoFonte(unittest.TestCase):
    def test_a_varredura_alcanca_o_repositorio(self):
        """Varredura que nao le nada nunca e varredura que funciona."""
        total = sum(1 for _ in _arquivos())
        self.assertGreater(total, 100, f"varri apenas {total} arquivos")

    def test_nenhum_arquivo_carrega_byte_de_controle(self):
        suspeitos = []
        for caminho in _arquivos():
            bruto = caminho.read_bytes()
            encontrados = sorted(
                {b for b in bruto if b < 0x20 and b not in PERMITIDOS}
            )
            if encontrados:
                suspeitos.append(
                    f"{caminho.relative_to(REPO)}: "
                    f"{[hex(b) for b in encontrados]}"
                )
        self.assertEqual(
            suspeitos,
            [],
            "byte de controle no fonte — invisivel no editor e capaz de "
            "transformar uma regex em algo que nunca casa:\n  "
            + "\n  ".join(suspeitos),
        )

    def test_a_varredura_realmente_pega_o_defeito_que_a_motivou(self):
        """O caso exato: backspace no lugar da ancora de palavra."""
        defeito = b'rf"(INSERT INTO|UPDATE)\\s+{tabela}\x08"'
        encontrados = [b for b in defeito if b < 0x20 and b not in PERMITIDOS]
        self.assertEqual(encontrados, [0x08])

    def test_a_varredura_nao_acusa_fonte_legitimo(self):
        legitimo = "def f():\n\treturn 1\r\n".encode("utf-8")
        encontrados = [b for b in legitimo if b < 0x20 and b not in PERMITIDOS]
        self.assertEqual(encontrados, [])


if __name__ == "__main__":
    unittest.main()
