# -*- coding: utf-8 -*-
"""A fronteira entre o Explica corporativo e o clinico.

O FROID Explica clinico exige aprovacao profissional, e injeta resumo da
CARTEIRA DE PACIENTES no contexto quando a pergunta e comparativa. Reaproveitar
aquela rota para responder duvida de empregador levaria dado clinico para o
lado errado da fronteira por um caminho que ninguem estaria olhando — nao por
uma decisao errada, mas por reuso que parecia economia.

Por isso o caminho corporativo e outro, de ponta a ponta: outra rota, outra
autorizacao, outra collection na ChromaDB, outro prompt. Este arquivo prende
cada uma dessas quatro separacoes.

A separacao por collection e a que mais importa. Filtro de metadado seria uma
condicao que alguem pode esquecer numa consulta nova; collection separada e uma
condicao que nao existe para ser esquecida — abrir a errada devolve vazio, em
vez de devolver o que nao devia.
"""

from __future__ import annotations

import ast
import io
import sys
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

MAIN = io.open(SERVER / "main.py", encoding="utf-8").read()
MODULO = io.open(SERVER / "nr1_explica.py", encoding="utf-8").read()
INDEXADOR = io.open(
    SERVER / "tools" / "indexar_nr1_explica.py", encoding="utf-8"
).read()

import nr1_explica  # noqa: E402


def _codigo(fonte: str, nome: str) -> str:
    """O corpo da funcao SEM a docstring.

    As asserçoes negativas precisam disso: as docstrings deste modulo explicam
    a fronteira citando pelo nome exatamente o que nao pode ser chamado, e e
    assim que devem continuar.
    """
    arvore = ast.parse(fonte)
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
            return "\n".join(
                ast.get_source_segment(fonte, item) or "" for item in corpo
            )
    raise AssertionError(f"funcao {nome!r} nao encontrada")


class OAcervoENoutraCollection(unittest.TestCase):
    def test_a_collection_do_nr1_nao_e_a_clinica(self):
        self.assertNotEqual(nr1_explica.COLLECTION, nr1_explica.COLLECTION_CLINICA)

    def test_o_modulo_recusa_se_as_duas_coincidirem(self):
        # Cinto e suspensorio: as duas vem de variavel de ambiente, e um deploy
        # pode iguala-las por engano.
        codigo = _codigo(MODULO, "_refuse_if_clinical_collection")
        self.assertIn("raise RuntimeError", codigo)

    def test_o_indexador_recusa_escrever_na_collection_clinica(self):
        self.assertIn("RECUSADO", INDEXADOR)
        self.assertIn("COLLECTION_CLINICA", INDEXADOR)

    def test_o_indexador_recusa_pareceres(self):
        # Parecer da nossa assessoria sobre os NOSSOS contratos nao e fonte
        # citavel ao cliente: e opiniao sobre documento nosso, nao norma.
        codigo = _codigo(INDEXADOR, "recusar_o_que_nao_pode_entrar")
        self.assertIn("pareceres", codigo)
        self.assertIn("SystemExit", codigo)

    def test_o_indexador_recusa_nota_clinica(self):
        codigo = _codigo(INDEXADOR, "recusar_o_que_nao_pode_entrar")
        self.assertIn("FROID_NR1_", codigo)


class ABuscaNaoTemPortaParaDadoClinico(unittest.TestCase):
    def test_buscar_recebe_apenas_texto(self):
        # Se um dia alguem acrescentar `context` ou `patient_id` aqui, o dado
        # entra no prompt sem que nenhuma outra trava perceba.
        import inspect

        assinatura = inspect.signature(nr1_explica.buscar)
        self.assertEqual(list(assinatura.parameters), ["pergunta", "limite"])

    def test_o_modulo_nao_manipula_dado_clinico(self):
        """Nenhum NOME do codigo fala de paciente, sessao ou carteira.

        Conferido sobre os identificadores, e nao sobre o texto do arquivo: a
        documentacao do modulo explica a fronteira citando exatamente essas
        palavras, e e assim que ela deve continuar. Teste que proibisse a
        palavra estaria proibindo a explicacao.
        """
        arvore = ast.parse(MODULO)
        nomes: set[str] = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Name):
                nomes.add(no.id.lower())
            elif isinstance(no, ast.Attribute):
                nomes.add(no.attr.lower())
            elif isinstance(no, ast.arg):
                nomes.add(no.arg.lower())
            elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nomes.add(no.name.lower())
        for proibido in ("patient", "paciente", "portfolio", "carteira", "sessao"):
            for nome in nomes:
                self.assertNotIn(
                    proibido, nome, f"nr1_explica manipula {nome}"
                )

    def test_a_instrucao_proibe_falar_de_pessoa_identificada(self):
        instrucao = nr1_explica.INSTRUCAO.lower()
        self.assertIn("recuse", instrucao)
        self.assertIn("prontuario", instrucao)
        self.assertIn("dado de pessoa identificada", instrucao)
        self.assertIn("invente", instrucao)


class ARotaCorporativaNaoUsaOPortaoClinico(unittest.TestCase):
    def test_usa_contexto_enterprise_e_nao_aprovacao_profissional(self):
        codigo = _codigo(MAIN, "nr1_explica_query")
        self.assertIn("_require_enterprise_context", codigo)
        self.assertNotIn("_require_professional_feature_access", codigo)

    def test_nao_injeta_carteira_nem_contexto_de_sessao(self):
        codigo = _codigo(MAIN, "nr1_explica_query")
        for proibido in (
            "_build_portfolio_summary",
            "_format_session_context",
            "_format_session_transcript",
            "_is_comparative_question",
        ):
            self.assertNotIn(proibido, codigo)

    def test_nao_reaproveita_a_busca_clinica(self):
        codigo = _codigo(MAIN, "nr1_explica_query")
        self.assertNotIn("_query_chroma_froid_knowledge", codigo)
        self.assertNotIn("_query_froid_knowledge", codigo)
        self.assertIn("nr1_explica.preparar", codigo)

    def test_acervo_ausente_devolve_estado_e_nao_erro(self):
        # A tela tem conteudo curado proprio e continua respondendo sem esta
        # rota. Erro 500 no meio de uma reuniao seria pior do que responder
        # menos.
        codigo = _codigo(MAIN, "nr1_explica_query")
        self.assertIn('"disponivel": False', codigo)
        self.assertIn("acervo_nao_indexado", codigo)

    def test_a_rota_clinica_continua_exigindo_profissional(self):
        # Regressao no outro sentido: afrouxar a rota clinica para "reusar"
        # tambem quebraria a fronteira.
        codigo = _codigo(MAIN, "froid_explica_query")
        self.assertIn("_require_professional_feature_access", codigo)


if __name__ == "__main__":
    unittest.main()
