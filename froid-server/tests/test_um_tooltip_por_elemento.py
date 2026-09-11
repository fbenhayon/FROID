"""Nenhum elemento carrega o `title` nativo E um tooltip próprio.

Os dois desenham a mesma informação, e o nativo — caixa de fundo branco do
sistema, posicionada pelo cursor — ignora a largura do card e cobre o vizinho.
Onde existe o painel estilizado, o `title` sai; o `aria-label` preserva o texto
para o leitor de tela, então nada se perde em acessibilidade.

O par apareceu em duas telas, e as duas nasceram do mesmo commit: o road map do
Nr1Dashboard (corrigido em 90bdf5b7) e o mapa de evidências do Nr1Dossier
(corrigido em 11/09/2026). Este arquivo varre pela REGRA e não pelas duas que eu
vi — procurar só por elas deixaria a terceira passar.
"""

import re
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
PAINEL = SERVER_DIR.parent / "froid-dashboard" / "src"


class UmTooltipPorElemento(unittest.TestCase):
    def _telas_com_tooltip_proprio(self):
        for caminho in sorted(PAINEL.rglob("*.tsx")):
            if ".test." in caminho.name:
                continue
            texto = caminho.read_text(encoding="utf-8")
            if 'role="tooltip"' in texto:
                yield caminho, texto

    def test_nenhum_elemento_com_tooltip_proprio_tambem_usa_title(self):
        telas = list(self._telas_com_tooltip_proprio())
        self.assertTrue(telas, "nenhuma tela com tooltip proprio — varredura vazia")
        for caminho, texto in telas:
            with self.subTest(tela=caminho.name):
                # O elemento que ANCORA o tooltip proprio e o que tem
                # `group relative`. Um `title` dentro da mesma abertura de tag
                # e o par duplicado.
                for bloco in re.findall(r"<[a-zA-Z][^>]*group relative[^>]*>", texto):
                    self.assertNotIn(
                        "title=",
                        bloco,
                        f"{caminho.name}: elemento ancora um tooltip proprio e ainda "
                        "carrega o title nativo",
                    )

    def test_o_road_map_e_o_dossie_ficaram_so_com_o_painel(self):
        """As duas telas do incidente, nomeadas, com a garantia de cada uma."""
        roadmap = (PAINEL / "pages" / "Nr1Dashboard.tsx").read_text(encoding="utf-8")
        self.assertNotIn("title={passo.entrega}", roadmap)
        self.assertIn("${passo.detalhe}. ${passo.entrega}", roadmap)
        self.assertIn('role="tooltip"', roadmap)

        dossie = (PAINEL / "pages" / "Nr1Dossier.tsx").read_text(encoding="utf-8")
        self.assertNotIn("title={meta.detail}", dossie)
        self.assertIn("${meta.label}. ${meta.detail}", dossie)
        self.assertIn('role="tooltip"', dossie)


if __name__ == "__main__":
    unittest.main()
