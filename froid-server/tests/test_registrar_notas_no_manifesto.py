# -*- coding: utf-8 -*-
"""Nota liberada em git chega ao manifesto de ingestao, e so ela.

19/10/2026: FROID_Dois_Produtos_Clinico_e_NR1.md estava liberada em git e
ausente do manifesto de producao — nunca entrou na busca vetorial, sem erro.
A ferramenta registra o que falta; o teste afirma que ela cria so entradas
novas, com indexar=true e o caminho real, e nunca mexe no que ja existe.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parents[1]
TOOLS = SERVIDOR / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from liberar_notas_froid import LIBERADAS  # noqa: E402
from registrar_notas_no_manifesto import APPROVED, faltantes  # noqa: E402


class ORegistroDasNotas(unittest.TestCase):
    def test_cria_so_o_que_falta_com_indexar_true_e_caminho_real(self):
        existente = {"FROID_Ficha_Tecnica_IPM.md": {"indexar": False, "motivo": "x", "caminho": "y", "categorias": []}}
        novas = faltantes(existente)
        self.assertNotIn("FROID_Ficha_Tecnica_IPM.md", novas)
        self.assertIn("FROID_Clinica_Papeis_Agenda_Cotas_Visibilidade.md", novas)
        self.assertIn("FROID_Explica_O_Que_Consulta_E_Como_Responde.md", novas)
        self.assertIn("FROID_Dois_Produtos_Clinico_e_NR1.md", novas)
        for nome, entrada in novas.items():
            self.assertTrue(entrada["indexar"], nome)
            self.assertTrue(Path(entrada["caminho"]).exists(), nome)
            self.assertEqual(entrada["motivo"], LIBERADAS[nome])

    def test_toda_nota_liberada_existe_em_disco(self):
        # Liberar nome que nao existe e promessa vazia: a ferramenta a ignora,
        # e este teste e quem acusa.
        for nome in LIBERADAS:
            self.assertTrue(list(APPROVED.rglob(nome)), f"{nome} liberada e ausente em knowledge/approved")

    def test_a_linha_de_comando_grava_e_e_idempotente(self):
        with tempfile.TemporaryDirectory() as pasta:
            manifesto = Path(pasta) / "manifesto.json"
            manifesto.write_text(json.dumps({"FROID_Ficha_Tecnica_IPM.md": {"indexar": True, "motivo": "m", "caminho": "c", "categorias": []}}), encoding="utf-8")
            comando = [sys.executable, str(TOOLS / "registrar_notas_no_manifesto.py"), "--manifesto", str(manifesto)]
            primeira = subprocess.run(comando, capture_output=True, text=True, check=True)
            self.assertIn("Manifesto gravado", primeira.stdout)
            dados = json.loads(manifesto.read_text(encoding="utf-8"))
            self.assertTrue(dados["FROID_Clinica_Papeis_Agenda_Cotas_Visibilidade.md"]["indexar"])
            self.assertEqual(dados["FROID_Ficha_Tecnica_IPM.md"]["caminho"], "c")
            segunda = subprocess.run(comando, capture_output=True, text=True, check=True)
            self.assertIn("Nenhuma nota liberada falta", segunda.stdout)


if __name__ == "__main__":
    unittest.main()
