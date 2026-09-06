# -*- coding: utf-8 -*-
"""A base interna que o FROID Explica clinico recupera e injeta no prompt.

Estas linhas nao sao documentacao: elas entram no prompt rotuladas como "Fonte
interna FROID" e o modelo as trata como afirmacao da casa. Revisadas em
06/09/2026 contra o que o codigo calcula, quatro estavam erradas — jitter
descrito como derivado de ZCR, shimmer descrito pelo ramo de substituicao, e
duas afirmando fisiologia que o FROID nao mede (tremor do sistema nervoso
autonomo, retraumatizacao).

O efeito nao era teorico. O modelo recebia, no mesmo prompt, uma fonte interna
afirmando correlato clinico e uma instrucao proibindo diagnosticar; dividia a
diferenca, e devolvia a ressalva generica que o profissional reclamou.

Este arquivo trava a regra, e nao a ocorrencia: varre a BASE INTEIRA em busca
das afirmacoes retiradas, e nao apenas as quatro entradas que as continham.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

with io.open(SERVIDOR / "main.py", encoding="utf-8") as arquivo:
    MAIN = arquivo.read()


def _constante(nome: str) -> dict:
    """Le a constante do fonte, sem importar main.py.

    `main.py` sobe FastAPI, banco e estado de identidade no import; ler pelo
    parser mantem o teste barato e independente de ambiente.
    """
    import ast

    for no in ast.parse(MAIN).body:
        if (
            isinstance(no, ast.Assign)
            and getattr(no.targets[0], "id", "") == nome
        ):
            return ast.literal_eval(no.value)
    raise AssertionError(f"constante {nome!r} nao encontrada")


BASE = _constante("KNOWLEDGE_BASE")
ROTULOS = _constante("KNOWLEDGE_SOURCE_LABELS")

# As afirmacoes retiradas, com o motivo. Nao voltam por copiar e colar de uma
# versao antiga do arquivo.
AFIRMACOES_RETIRADAS = {
    "derivado de ZCR": "jitter nao deriva de ZCR em ramo nenhum do motor",
    "envelope RMS": "descrevia so o ramo de substituicao do shimmer",
    "risco depressivo": "nenhum coeficiente cepstral tem limiar clinico",
    "ansiedade somatica": "nao ha estudo publicado que sustente a associacao",
    "retraumatizacao": "o FROID nao mede sobrecarga nem trauma",
    "ativacao de mania": "afirmacao clinica sem citacao, com peso de fonte interna",
    "tremores do sistema nervoso": "sub-harmonicos descrevem estrutura temporal do sinal",
}


class TodaEntradaTemRotulo(unittest.TestCase):
    def test_nenhuma_chave_fica_sem_rotulo(self):
        """Sem rotulo, a citacao sai com o NOME DO CAMPO na cara do usuario.

        Era o caso de `sub_harmonicos`, `facs_trauma`, `mania_ativacao` e
        `governanca_lgpd`: `KNOWLEDGE_SOURCE_LABELS.get(chave, chave)` devolvia
        a chave crua.
        """
        self.assertEqual(sorted(set(BASE) - set(ROTULOS)), [])

    def test_nenhum_rotulo_aponta_para_entrada_que_nao_existe(self):
        self.assertEqual(sorted(set(ROTULOS) - set(BASE)), [])


class ABaseNaoAfirmaOQueOFroidNaoMede(unittest.TestCase):
    def test_as_afirmacoes_retiradas_nao_voltam(self):
        # A varredura e sobre a base inteira de proposito: corrigir a ocorrencia
        # e nao a regra ja deixou quatro `|| "neutro"` no mesmo arquivo.
        for trecho, motivo in AFIRMACOES_RETIRADAS.items():
            with self.subTest(trecho=trecho):
                encontradas = [
                    chave for chave, texto in BASE.items() if trecho.lower() in texto.lower()
                ]
                self.assertEqual(encontradas, [], f"{trecho!r}: {motivo}")

    def test_a_lapide_da_entrada_removida_continua_no_arquivo(self):
        # O registro do que foi tirado e por que e o que impede a reintroducao
        # por ignorancia. Ver secao 4 do rigor de engenharia.
        self.assertIn('Aqui existia "mania_ativacao"', MAIN)

    def test_a_chave_tambem_nao_afirma(self):
        # A chave aparece como `source` em /api/knowledge. "mfcc7_depressao"
        # afirmava um construto clinico no proprio nome do campo.
        for chave in BASE:
            with self.subTest(chave=chave):
                self.assertNotIn("depressao", chave)
                self.assertNotIn("ansiedade", chave)
                self.assertNotIn("trauma", chave)
                self.assertNotIn("mania", chave)


class AsCitacoesContinuamSeparadas(unittest.TestCase):
    """O filtro de citacao so deixa passar referencia cientifica. Rotulo interno
    que passasse pelo filtro apareceria ao profissional como se fosse artigo."""

    def _filtro(self):
        import re
        import unicodedata

        marcadores = _constante("SCIENTIFIC_CITATION_MARKERS")

        def normalizar(texto: str) -> str:
            return re.sub(r"\s+", " ", str(texto or "").lower()).strip()

        return lambda citacao: any(m in normalizar(citacao) for m in marcadores)

    def test_todo_rotulo_de_referencia_passa_pelo_filtro(self):
        e_cientifica = self._filtro()
        for chave, rotulo in ROTULOS.items():
            if not chave.startswith("ref_"):
                continue
            with self.subTest(chave=chave):
                self.assertTrue(e_cientifica(rotulo), f"{rotulo!r} nao seria citado")

    def test_nenhum_rotulo_interno_passa_pelo_filtro(self):
        e_cientifica = self._filtro()
        vazando = [
            rotulo
            for chave, rotulo in ROTULOS.items()
            if not chave.startswith("ref_") and e_cientifica(rotulo)
        ]
        self.assertEqual(vazando, [], "fonte interna sairia listada como referencia cientifica")


class ABaseDescreveOQueOCodigoFaz(unittest.TestCase):
    def test_jitter_e_shimmer_declaram_a_unidade_de_analise(self):
        # A ressalva que importa: o quadro, e nao o ciclo glotal. E ela que
        # impede o profissional de comparar com limiar do Praat.
        for chave in ("jitter_bioacustico", "shimmer_bioacustico"):
            with self.subTest(chave=chave):
                self.assertIn("quadros vozeados", BASE[chave])

    def test_as_bandas_declaram_que_nao_sao_eeg(self):
        self.assertIn("nao mede atividade cerebral", BASE["bandas_de_modulacao"])

    def test_os_indices_dna_declaram_o_limite_inferior(self):
        # O clip em zero e a informacao que mais falta a quem le: queda abaixo
        # da base e estar na base produzem o mesmo 0.
        self.assertIn("nao pode ser negativo", BASE["indices_dna"])

    def test_a_base_declara_que_branco_significa_nao_medido(self):
        self.assertIn("NAO MEDIDO", BASE["procedencia_da_medida"])


if __name__ == "__main__":
    unittest.main()
