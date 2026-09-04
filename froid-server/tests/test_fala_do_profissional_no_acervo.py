"""A fala do profissional entra no acervo; a identidade de ninguém entra.

O acervo tinha as colunas certas e nenhuma palavra dentro. `cut_summary_anon`,
`patient_summary_anon` e `professional_summary_anon` existiam no esquema desde o
começo, e o `INSERT` gravava string vazia nas três. O único sanitizador
disponível, `_anonymous_category`, recusa qualquer texto com mais de seis
palavras — foi feito para deixar passar rótulo de taxonomia e barrar discurso.

Ou seja: o lugar da fala existia e a camada que o preenche não. Os prompts do
FROID Explica perguntariam a uma base que só sabia responder "intervencao_geral".

O que este arquivo guarda são as duas metades da decisão de 04/09/2026:

1. A fala do PROFISSIONAL entra com a FORMA preservada e as referências
   trocadas por marcador — porque é a forma que ensina a técnica a quem
   consulta depois. A do PACIENTE não entra literal em forma nenhuma.

2. Quando a limpeza não tem certeza, não se guarda nada — e o motivo fica
   registrado. Acervo vazio sem motivo é indistinguível de acervo que ninguém
   alimentou.
"""

import ast
import io
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from froid_deidentify import (  # noqa: E402
    MINIMO_DE_PALAVRAS,
    TAXA_MAXIMA_DE_REDACAO,
    VERSAO_DEID,
    desidentificar_fala,
)

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")


class AFormaFicaEAReferenciaSai(unittest.TestCase):
    """O ponto inteiro do desenho: o que ensina a técnica é a construção da
    frase; o que identifica alguém é o referente. Os dois são separáveis."""

    def test_a_construcao_da_frase_sobrevive_inteira(self):
        texto, motivo = desidentificar_fala(
            "E se você observasse isso sem responder, como fez com a Nathalie em maio?"
        )
        self.assertEqual(motivo, "ok")
        # A técnica: a pergunta hipotética, o verbo, a ordem.
        self.assertIn("E se você observasse isso sem responder", texto)
        # O referente: some, mas deixa o tipo no lugar.
        self.assertNotIn("Nathalie", texto)
        self.assertIn("[NOME]", texto)
        self.assertIn("[DATA]", texto)

    def test_o_verbo_principal_NAO_e_apagado(self):
        """A primeira versão redigia "[NOME] que ele reparasse na respiração":
        apagou o verbo por ele abrir período em maiúscula. Apagar o verbo não é
        ser conservador — é destruir o registro e ainda sugerir que ali havia um
        nome."""
        texto, motivo = desidentificar_fala(
            "Sugeri que ele reparasse na respiração antes de responder, sem julgar."
        )
        self.assertEqual(motivo, "ok")
        self.assertTrue(texto.startswith("Sugeri que ele reparasse"))

    def test_o_parentesco_fica_porque_e_clinico_e_nao_identifica(self):
        texto, _ = desidentificar_fala(
            "Ele me disse que a filha dele evita o assunto quando o pai levanta a voz."
        )
        self.assertIn("a filha dele", texto)

    def test_identificador_estruturado_nao_depende_de_julgamento(self):
        for entrada in (
            "Combinei de escrever para ele no endereco teste@exemplo.com depois da sessao.",
            "Anotei o telefone dele, que e 21 99999-8888, para retomar isso depois.",
            "O documento dele e 123.456.789-00 e ficou registrado na ficha da clinica.",
        ):
            with self.subTest(entrada=entrada[:30]):
                texto, _ = desidentificar_fala(entrada)
                self.assertNotIn("@exemplo", texto)
                self.assertNotIn("99999", texto)
                self.assertNotIn("123.456", texto)


class NaDuvidaNaoSeGuardaNada(unittest.TestCase):
    """Falha fechada, com o motivo dito. Meia frase é pior do que frase nenhuma:
    quem lê o acervo não tem como saber o que faltou."""

    def test_comeco_de_periodo_ambiguo_derruba_a_fala_inteira(self):
        """"Sofia contou isso" e "Sugeri que ele contasse" têm a mesma forma. Sem
        dicionário, a distinção não existe — e inventá-la seria supor."""
        texto, motivo = desidentificar_fala(
            "Sofia contou isso na sessao passada, e voce reagiu do mesmo jeito."
        )
        self.assertEqual(texto, "")
        self.assertEqual(motivo, "inicio_ambiguo")

    def test_fala_curta_demais_nao_carrega_tecnica(self):
        self.assertEqual(desidentificar_fala("Sim, entendi.")[1], "curta_demais")

    def test_fala_referencial_demais_vira_queijo_suico(self):
        texto, motivo = desidentificar_fala(
            "O Joao e a Maria moram em Petropolis desde 2019, e a Ana ligou ontem."
        )
        self.assertEqual(texto, "")
        self.assertEqual(motivo, "referencial_demais")

    def test_o_teto_de_redacao_e_explicito_e_nao_magico(self):
        self.assertLessEqual(TAXA_MAXIMA_DE_REDACAO, 0.5)
        self.assertGreaterEqual(MINIMO_DE_PALAVRAS, 3)

    def test_texto_vazio_e_dito_vazio(self):
        self.assertEqual(desidentificar_fala("")[1], "vazio")

    def test_toda_recusa_devolve_string_vazia_e_nunca_parcial(self):
        for entrada in ("", "ok", "Sofia disse isso ontem para o irmao dela aqui."):
            texto, motivo = desidentificar_fala(entrada)
            if motivo != "ok":
                with self.subTest(motivo=motivo):
                    self.assertEqual(texto, "")


class OAcervoRecebeAFalaDoProfissional(unittest.TestCase):
    def test_o_caminho_esta_DESLIGADO_por_padrao(self):
        """A garantia anterior era "nenhuma fala literal entra no acervo", com
        teste de seguranca proprio. Trocar isso e decisao do dono, e ate ela ser
        tomada o acervo grava o que sempre gravou."""
        self.assertIn('os.getenv("FROID_DATAMART_FALA_PROFISSIONAL", "0")', MAIN)
        self.assertIn('professional_summary_anon, motivo_deid = "", "desligado"', MAIN)

    def test_a_coluna_do_profissional_deixou_de_ser_string_vazia(self):
        self.assertIn("professional_summary_anon,\n                    motivo_deid", MAIN)

    def test_a_fala_do_PACIENTE_continua_fora(self):
        """A assimetria é a decisão, não um esquecimento: a fala do profissional
        é o ofício, a do paciente é a pessoa."""
        self.assertIn("patient_summary_anon: a fala do paciente NAO entra", MAIN)

    def test_o_motivo_da_recusa_e_gravado(self):
        """Sem isto, acervo vazio fica indistinguível de acervo que ninguém
        alimentou — e a diferença só apareceria quando alguém consultasse."""
        self.assertIn('"professional_deid_reason": "VARCHAR"', MAIN)
        self.assertIn('"professional_deid_version": "VARCHAR"', MAIN)
        self.assertIn("VERSAO_DEID", MAIN)

    def test_a_versao_do_pipeline_acompanha_a_linha(self):
        """Regra de limpeza muda com o tempo. Sem a versão gravada, não há como
        reprocessar só o que foi escrito pela regra antiga."""
        self.assertTrue(VERSAO_DEID.startswith("deid-"))


def _classificador():
    """Extrai `_infer_intervention_category` de main.py e o executa isolado.

    `main.py` importa fastapi, que não existe na máquina de desenvolvimento.
    Recortar por número de linha já quebrou testes deste repositório duas vezes;
    aqui o recorte é pelo parser do Python, pelos NOMES das definições — imune a
    reindentação, a comentário novo e a mudança de vizinhança.
    """
    import re
    import unicodedata

    arvore = ast.parse((SERVER_DIR / "main.py").read_text(encoding="utf-8"))
    queridos = {
        "_sem_acento_simples",
        "BALDES_DE_INTERVENCAO",
        "PISO_DE_EVIDENCIA",
        "_infer_intervention_category",
    }
    corpo = []
    for no in arvore.body:
        nome = getattr(no, "name", None)
        if nome is None and isinstance(no, ast.Assign):
            alvo = no.targets[0]
            nome = getattr(alvo, "id", None)
        if nome is None and isinstance(no, ast.AnnAssign):
            nome = getattr(no.target, "id", None)
        if nome in queridos:
            corpo.append(no)
    assert len(corpo) == len(queridos), f"faltou definicao: {len(corpo)}/{len(queridos)}"
    espaco: dict = {"re": re, "unicodedata": unicodedata}
    exec(compile(ast.Module(body=corpo, type_ignores=[]), "<main>", "exec"), espaco)
    return espaco["_infer_intervention_category"]


class OClassificadorDeIntervencaoDiscrimina(unittest.TestCase):
    """A coluna que o FROID Explica vai consultar primeiro.

    A versão anterior tinha três defeitos que se somavam, e o resultado prático
    era uma coluna que não separava nada:

    - `"?"` no balde `pergunta_aberta`. Como quase toda intervenção clínica
      contém uma pergunta, aquele balde engolia o acervo inteiro.
    - casamento por substring: "como" dentro de "comodidade", "corpo" dentro de
      "corporativo", "evita" dentro de "evitável".
    - empate decidido pela ORDEM DA LISTA, o que é um critério — mas não um
      critério sobre o texto.
    """

    def setUp(self):
        self.classificar = _classificador()

    def test_reconhece_cada_familia_de_intervencao(self):
        casos = (
            ("E o que você acha que aconteceria se não respondesse na hora?", "pergunta_aberta"),
            ("Vamos com calma, estou aqui, pode falar.", "acolhimento"),
            ("Isso faz sentido, e é natural sentir assim depois do que houve.", "validacao_emocional"),
            ("Repare esse padrão: você evita o assunto sempre que ele aparece.", "confrontacao_terapeutica"),
            ("Resumindo, na próxima sessão retomamos isso, combinamos?", "encerramento_sintese"),
        )
        for texto, esperado in casos:
            with self.subTest(esperado=esperado):
                self.assertEqual(self.classificar(texto), esperado)

    def test_substring_dentro_de_outra_palavra_nao_classifica(self):
        """"comodidade" contém "como"; "corporativo" contém "corpo"."""
        self.assertEqual(
            self.classificar("Ele trabalha numa empresa com boa comodidade e ambiente corporativo."),
            "intervencao_geral",
        )

    def test_interrogacao_sozinha_nao_e_pergunta_aberta(self):
        self.assertNotEqual(self.classificar("Tudo bem?"), "pergunta_aberta")

    def test_indicio_fraco_nao_classifica(self):
        """Uma palavra solta não é evidência. A única coisa pior do que não
        classificar é classificar errado, porque a linha entra no acervo com a
        mesma aparência de uma classificada com certeza."""
        self.assertEqual(self.classificar("Pausa."), "intervencao_geral")

    def test_texto_vazio_e_dito_nao_classificado(self):
        self.assertEqual(self.classificar(""), "nao_classificada")

    def test_acento_na_fala_nao_impede_o_casamento(self):
        """A transcrição vem acentuada; os indícios são escritos sem acento."""
        self.assertEqual(
            self.classificar("Isso faz sentido, e é natural sentir assim."),
            "validacao_emocional",
        )


class OINSERTDoAcervoESTAEquilibrado(unittest.TestCase):
    """O teste que existe porque o outro não roda.

    `test_data_froid_privacy_runtime` exercita a gravação de verdade — e é
    pulado inteiro quando o duckdb não está instalado, que é o caso da máquina
    de desenvolvimento. Uma coluna a mais na lista e um valor a menos passariam
    por toda a bateria local e só quebrariam em produção, no fim de uma sessão
    real, gravando nada.

    Este aqui lê o `INSERT` com o parser do Python e conta os três lados.
    """

    def _insert_do_acervo(self):
        arvore = ast.parse(io.open(SERVER_DIR / "main.py", encoding="utf-8").read())
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            if not (isinstance(no.func, ast.Attribute) and no.func.attr == "execute"):
                continue
            if not no.args or not isinstance(no.args[0], ast.Constant):
                continue
            if "INSERT INTO anonymous_session_cuts" in str(no.args[0].value):
                return no
        self.fail("nao achei o INSERT do acervo")

    def test_colunas_placeholders_e_valores_batem(self):
        no = self._insert_do_acervo()
        sql = str(no.args[0].value)
        colunas = sql[sql.index("(") + 1 : sql.index(")")]
        n_colunas = len([c for c in colunas.split(",") if c.strip()])
        n_placeholders = sql.count("?")
        self.assertGreater(len(no.args), 1, "INSERT sem lista de valores")
        self.assertIsInstance(no.args[1], ast.List)
        n_valores = len(no.args[1].elts)
        self.assertEqual(n_colunas, n_placeholders, "colunas != placeholders")
        self.assertEqual(n_colunas, n_valores, "colunas != valores")


if __name__ == "__main__":
    unittest.main()
