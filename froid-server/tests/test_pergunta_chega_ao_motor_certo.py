# -*- coding: utf-8 -*-
"""A pergunta do profissional tem de chegar ao motor que a responde.

O FROID Explica clinico tem dois caminhos: o acervo clinico da propria sessao e
o acervo ANONIMO agregado. Quem decide e `_classify_froid_explica_intent`, e
ele decidia errado de duas maneiras — as duas silenciosas, porque a resposta
chega igualmente bem escrita vindo do motor errado.

1. **Precedencia invertida.** Os marcadores de sessao eram testados primeiro, e
   um deles e a string "ipm". "Como o IPM medio deste paciente se compara ao da
   BASE ANONIMA?" virava pergunta de sessao antes de a base anonima ser
   considerada.
2. **Acento.** A comparacao usava `_normalize_search_text`, que baixa a caixa e
   colapsa espaco mas nao tira acento. "base anônima", como se escreve em
   portugues, nunca casava com o marcador "base anonima". Nem "desta sessão"
   com "desta sessao".

Este arquivo trava as duas, e trava tambem os ATALHOS do painel: botao que
promete o que o acervo nao tem produz exatamente a resposta esquiva que o
profissional reclamou, e a culpa parece do assistente.
"""

from __future__ import annotations

import io
import re
import sys
import unittest
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

RAIZ = SERVIDOR.parent
AI_INSIGHTS = RAIZ / "froid-dashboard" / "src" / "components" / "panels" / "AIInsights.tsx"

import explica_clinico  # noqa: E402

with io.open(SERVIDOR / "main.py", encoding="utf-8") as arquivo:
    MAIN = arquivo.read()
with io.open(AI_INSIGHTS, encoding="utf-8") as arquivo:
    INSIGHTS = arquivo.read()


def classificador():
    """O classificador de verdade, sem subir o FastAPI.

    Importar main.py levanta app, banco e estado de identidade. Aqui so o
    trecho do classificador e compilado, com as suas dependencias reais
    injetadas — nao uma reimplementacao, que testaria a copia e nao o codigo.
    """
    inicio = MAIN.index("_MARCADORES_ANALYTICS")
    fim = MAIN.index("def _fallback_froid_explica_result(")
    espaco: dict = {"explica_clinico": explica_clinico, "re": re}
    exec(compile(MAIN[inicio:fim], "main.py", "exec"), espaco)
    return espaco["_classify_froid_explica_intent"]


CLASSIFICAR = classificador()


def _corpo_sem_docstring(nome: str) -> str:
    """O corpo da funcao, sem a docstring.

    As docstrings desta casa contam o incidente citando pelo nome o que nao
    pode voltar; asserçao negativa sobre o texto inteiro proibiria o registro
    junto com o defeito.
    """
    import ast

    arvore = ast.parse(MAIN)
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            corpo = list(no.body)
            if (
                corpo
                and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)
                and isinstance(corpo[0].value.value, str)
            ):
                corpo = corpo[1:]
            return chr(10).join(
                ast.get_source_segment(MAIN, item) or "" for item in corpo
            )
    raise AssertionError(f"funcao {nome!r} nao encontrada")


def presets() -> list[str]:
    inicio = INSIGHTS.index("const PRESETS = [")
    fim = INSIGHTS.index("\n];", inicio)
    return re.findall(r'\{\s*text:\s*"([^"]+)"\s*\}', INSIGHTS[inicio:fim])


class ADeclaracaoExplicitaGanha(unittest.TestCase):
    def test_a_base_anonima_vence_o_nome_da_metrica(self):
        self.assertEqual(
            CLASSIFICAR("Como o IPM medio deste paciente se compara ao da base anonima?"),
            "analytics",
        )

    def test_o_acento_nao_muda_o_destino(self):
        com_acento = "Quantas sessões da base anônima sustentam essa comparação?"
        sem_acento = "Quantas sessoes da base anonima sustentam essa comparacao?"
        self.assertEqual(CLASSIFICAR(com_acento), "analytics")
        self.assertEqual(CLASSIFICAR(com_acento), CLASSIFICAR(sem_acento))

    def test_pergunta_de_sessao_continua_no_acervo_clinico(self):
        for pergunta in (
            "Explique a diferença entre IPM e IDM nesta sessão",
            "o que quer dizer isso IND. ESPECTRAL 0.110",
            "como interpreto ZONAS Zona 12",
        ):
            with self.subTest(pergunta=pergunta):
                self.assertEqual(CLASSIFICAR(pergunta), "knowledge")

    def test_o_classificador_usa_a_normalizacao_com_acento(self):
        # A regra, e nao a ocorrencia: se alguem voltar a usar
        # `_normalize_search_text` aqui, metade da tabela volta a ser decorativa.
        #
        # SEM a docstring, de proposito: ela cita o nome da funcao antiga para
        # contar o incidente, e uma asserçao negativa sobre o texto inteiro
        # proibiria justamente o registro que impede o defeito de voltar.
        corpo = _corpo_sem_docstring("_classify_froid_explica_intent")
        self.assertIn("explica_clinico.normalizar_pergunta", corpo)
        self.assertNotIn("_normalize_search_text", corpo)


class OsAtalhosPrometemOQueExiste(unittest.TestCase):
    def test_nenhum_atalho_pede_escore_de_risco(self):
        """`clinical_risk` foi retirado do motor de metricas por ser triagem.

        O botao sobreviveu a remocao e continuava oferecendo "acima ou abaixo da
        media em riscos clinicos" sobre uma coluna que nao existe.
        """
        for texto in presets():
            with self.subTest(texto=texto):
                self.assertNotIn("risco", texto.lower())

    def test_nenhum_atalho_promete_predicao(self):
        for texto in presets():
            with self.subTest(texto=texto):
                self.assertNotIn("predi", texto.lower())

    def test_nenhum_atalho_promete_medir_melhora(self):
        # O acervo anonimo guarda IPM, IDM, zona, dissonancias e cadencia.
        # Nenhuma delas e desfecho clinico.
        for texto in presets():
            with self.subTest(texto=texto):
                self.assertNotIn("melhora", texto.lower())

    def test_o_acervo_anonimo_de_fato_nao_tem_coluna_de_risco(self):
        # A afirmacao acima verificada contra o esquema, e nao de memoria.
        esquema = MAIN[MAIN.index("CREATE TABLE IF NOT EXISTS anonymous_sessions (") :][:4000]
        self.assertNotIn("clinical_risk", esquema)
        self.assertNotIn("risk_score", esquema)

    def test_todo_atalho_populacional_chega_ao_motor_populacional(self):
        populacionais = [t for t in presets() if "anônima" in t or "anonima" in t]
        self.assertTrue(populacionais, "o painel perdeu os atalhos de comparacao")
        for texto in populacionais:
            with self.subTest(texto=texto):
                self.assertEqual(CLASSIFICAR(texto), "analytics")

    def test_todo_atalho_de_sessao_chega_ao_acervo_clinico(self):
        de_sessao = [t for t in presets() if "anônima" not in t and "anonima" not in t]
        self.assertTrue(de_sessao)
        for texto in de_sessao:
            with self.subTest(texto=texto):
                self.assertEqual(CLASSIFICAR(texto), "knowledge")


if __name__ == "__main__":
    unittest.main()
