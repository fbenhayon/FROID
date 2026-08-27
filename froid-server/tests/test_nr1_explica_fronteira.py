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


class OContratoEntraCitado(unittest.TestCase):
    """O acervo conhece os documentos contratuais, e sabe como usa-los.

    Deixa-los de fora parecia prudente e nao era: a pergunta contratual chega
    na reuniao, e "nao encontrei" sobre o proprio contrato e pior do que
    responder. O que nao pode e o modelo REESCREVER clausula — o comprovante de
    aceite prova um sha256, e parafrase do fornecedor sobre as proprias
    obrigacoes vira uma segunda versao da mesma coisa, sem digital.

    A protecao migrou de "nao indexar" para "indexar e mandar citar".
    """

    def test_os_documentos_contratuais_entram_no_indice(self):
        self.assertIn("CHAVES_CONTRATUAIS", INDEXADOR)
        for chave in ("terms_nr1", "nr1_company_contract", "privacy"):
            self.assertIn(chave, INDEXADOR)

    def test_o_contrato_do_outro_produto_fica_de_fora(self):
        # professional_contract e organization_contract sao da trilha clinica.
        self.assertNotIn("professional_contract", INDEXADOR)
        self.assertNotIn("organization_contract", INDEXADOR)

    def test_o_texto_vem_da_fonte_canonica_e_nao_de_copia(self):
        # Copia envelheceria sozinha, e o comprovante prova a digital do texto
        # vigente. Cada trecho carrega versao e sha256 do documento.
        codigo = _codigo(INDEXADOR, "trechos_contratuais")
        self.assertIn("public_legal_catalog", codigo)
        self.assertIn("sha256", codigo)
        self.assertIn("versao", codigo)

    def test_a_clausula_e_indexada_inteira(self):
        # Uma secao por trecho: clausula cortada no meio afirma metade de uma
        # condicao, e a metade que sobra costuma ser a que favorece quem citou.
        codigo = _codigo(INDEXADOR, "trechos_contratuais")
        self.assertIn("sections", codigo)
        self.assertNotIn("chunk_markdown", codigo)

    def test_a_instrucao_manda_citar_e_nao_parafrasear(self):
        instrucao = nr1_explica.INSTRUCAO
        self.assertIn("'contrato'", instrucao)
        self.assertIn("ENTRE ASPAS", instrucao)
        self.assertIn("assessoria juridica", instrucao)

    def test_a_instrucao_recusa_estimar_preco_e_prazo(self):
        instrucao = nr1_explica.INSTRUCAO.lower()
        self.assertIn("proposta comercial", instrucao)
        self.assertIn("nao estime", instrucao)

    def test_a_citacao_declara_que_e_documento_contratual(self):
        trecho = nr1_explica.Trecho(
            texto="x", titulo="Contrato — Objeto", fonte="nr1_company_contract",
            classe="contrato",
        )
        self.assertIn("documento contratual vigente", trecho.rotulo)


class OAcervoNaoSobeSemANorma(unittest.TestCase):
    """A primeira indexacao em producao passou sem o texto da lei.

    O script rodou, imprimiu "Pronto: 163 trechos" e indexou tudo MENOS as
    normas — porque o Dockerfile do backend tem contexto ./froid-server e nao
    alcanca docs/normas na raiz do repositorio. Sucesso pela metade, em
    silencio, no mesmo padrao que este modulo ja produziu quatro vezes.

    Um acervo de NR-1 sem o texto da NR-1 responde a tudo citando a nossa
    propria documentacao — que e exatamente a fonte que um auditor nao aceita.
    """

    def test_o_indexador_recusa_indexar_sem_fonte_normativa(self):
        codigo = _codigo(INDEXADOR, "main")
        self.assertIn("normativas", codigo)
        self.assertIn("RECUSADO", codigo)
        self.assertIn("sem_normas", codigo)

    def test_o_indexador_procura_as_normas_no_ponto_de_montagem(self):
        # Dentro do conteiner docs/normas so existe montado; fora dele, vale o
        # caminho do repositorio. Procurar so um dos dois quebra num ambiente.
        codigo = _codigo(INDEXADOR, "_pasta_das_normas")
        self.assertIn("/normas", codigo)
        self.assertIn("REPO_DIR", codigo)

    def test_o_indexador_diz_onde_procurou(self):
        # Diagnostico impresso vale mais do que suposicao: foi a ausencia da
        # linha que fez a falha passar despercebida.
        codigo = _codigo(INDEXADOR, "main")
        self.assertIn("Normas em:", codigo)

    def test_o_compose_monta_as_normas_no_backend(self):
        compose = io.open(
            SERVER.parent / "docker-compose.yml", encoding="utf-8"
        ).read()
        self.assertIn("./docs/normas:/normas:ro", compose)


class OConferirRespondeSeEstaCompleto(unittest.TestCase):
    """--conferir precisa responder a unica pergunta que importa.

    A versao anterior imprimia o total e uma amostra de cinco linhas, que
    saiu cinco vezes do mesmo arquivo. Com ela na tela, um indice sem o texto
    da lei parecia saudavel: o total era razoavel e nao havia como ver o que
    faltava. Agora ele conta por classe de fonte e sai com codigo 1 quando
    falta norma.
    """

    def test_conta_por_classe_de_fonte(self):
        codigo = _codigo(INDEXADOR, "main")
        self.assertIn("Por classe de fonte", codigo)
        for classe in ("norma", "interpretacao", "contrato", "nota-froid"):
            self.assertIn(f'"{classe}"', codigo)

    def test_sai_com_erro_quando_falta_norma(self):
        # Codigo de saida importa: e o que um script de deploy consegue ler.
        codigo = _codigo(INDEXADOR, "main")
        self.assertIn("SEM TEXTO DE NORMA", codigo)
        self.assertIn("return 1", codigo)
