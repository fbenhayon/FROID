# -*- coding: utf-8 -*-
"""A pergunta sobre uma metrica nao pode cair no portao administrativo.

08/09/2026, relatado por um profissional em producao. Ele perguntou:

    "para que serve o DMFCC7 e como essa metrica pode me ajudar e agucar minha
     cultura para que possa ter uma sessao com mais conteudo e possibilidade de
     ajudar MEUS PACIENTES e resolverem suas questoes"

E recebeu:

    "1. Resultado disponivel
     - Pacientes ativos identificados no contexto atual: 2.
     - Total de pacientes no contexto atual: 2.\\n"

A pergunta nunca chegou ao acervo. `_is_operational_question` casa a expressao
"meus pacientes", que ali era oracao subordinada, e `_query_froid_knowledge`
devolvia o texto administrativo ANTES de qualquer recuperacao. A mesma coisa
aconteceu com "o indice Gama".

E o mesmo defeito de precedencia que ja tinha sido corrigido em
`_classify_froid_explica_intent` — e a prova de que ali eu corrigi o LUGAR e
nao a REGRA (secao 2.8): eram dois portoes, e so um foi consertado.

De quebra, o `\\n` visivel no fim da segunda linha: uma f-string aninhada com
barra dobrada imprimia a BARRA e o ENE na tela do profissional.
"""

from __future__ import annotations

import io
import re
import sys
import typing
import unittest
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

import explica_clinico  # noqa: E402

with io.open(SERVIDOR / "main.py", encoding="utf-8") as arquivo:
    MAIN = arquivo.read()


def _fatia(inicio: str, fim: str) -> str:
    return MAIN[MAIN.index(inicio) : MAIN.index(fim)]


def carregar():
    """As funcoes reais de main.py, sem subir o FastAPI.

    Compiladas do fonte, e nao reimplementadas: teste sobre copia defende a
    copia.
    """
    espaco: dict = {
        "re": re,
        "Dict": typing.Dict,
        "Any": typing.Any,
        "Optional": typing.Optional,
    }
    for inicio, fim in (
        ("def _normalize_search_text(", "async def _generate_froid_explain_text("),
        ("def _find_context_metric(", "_MARCADORES_ANALYTICS"),
        ("def _is_operational_question(", "def _retrieval_query_for_payload("),
        ("def _operational_fallback_result(", "async def _query_froid_knowledge("),
    ):
        exec(compile(_fatia(inicio, fim), "main.py", "exec"), espaco)
    return espaco


ESPACO = carregar()

# As duas perguntas exatas do relato, encurtadas so no que nao importa.
PERGUNTA_DMFCC7 = (
    "para que serve o DMFCC7 e como essa metrica pode me ajudar e agucar minha "
    "cultura para que possa ter uma sessao com mais conteudo e possibilidade de "
    "ajudar meus pacientes e resolverem suas questoes"
)
PERGUNTA_GAMA = (
    "para que serve o indice Gama e como essa metrica pode me ajudar e agucar "
    "minha cultura para que possa ter uma sessao com mais conteudo e "
    "possibilidade de ajudar meus pacientes e resolverem suas questoes"
)


class AMetricaGanhaDoPortaoAdministrativo(unittest.TestCase):
    def test_as_perguntas_do_relato_nomeiam_um_indice(self):
        # Se esta asserçao cair, o portao nao e o problema: o de-para e.
        self.assertEqual(
            [i.rotulo for i in explica_clinico.indices_citados(PERGUNTA_DMFCC7)],
            ["DMFCC7"],
        )
        self.assertEqual(
            [i.rotulo for i in explica_clinico.indices_citados(PERGUNTA_GAMA)],
            ["GAMA"],
        )

    def test_o_portao_administrativo_ainda_casa_a_expressao(self):
        """O portao nao mudou, e nao devia mudar.

        "meus pacientes" continua sendo marcador administrativo legitimo. O que
        mudou foi QUEM decide primeiro.
        """
        self.assertTrue(ESPACO["_is_operational_question"](PERGUNTA_DMFCC7))

    def test_o_endpoint_consulta_a_metrica_antes_do_portao(self):
        corpo = _fatia(
            "async def _query_froid_knowledge(", "SQL_FORBIDDEN_RE = re.compile("
        )
        self.assertIn("pergunta_sobre_metrica", corpo)
        self.assertIn("explica_clinico.indices_citados(payload.query_text)", corpo)
        self.assertIn("explica_clinico.zonas_citadas(payload.query_text)", corpo)
        self.assertIn("and not pergunta_sobre_metrica", corpo)

        # A ordem importa: a guarda tem de ser avaliada ANTES da chamada.
        self.assertLess(
            corpo.index("pergunta_sobre_metrica = bool("),
            corpo.index("_operational_fallback_result(payload.query_text"),
        )

    def test_pergunta_administrativa_de_verdade_continua_atendida(self):
        """Nao e para desligar o portao — e para ele parar de atropelar.

        "quantos pacientes ativos eu tenho" nao nomeia indice nenhum e continua
        indo para o caminho administrativo.
        """
        pergunta = "quantos pacientes ativos eu tenho hoje"
        self.assertEqual(explica_clinico.indices_citados(pergunta), [])
        self.assertTrue(ESPACO["_is_operational_question"](pergunta))
        resposta = ESPACO["_operational_fallback_result"](
            pergunta, {"active_patients_count": 2, "patients_count": 2}
        )
        self.assertIn("Pacientes ativos identificados", resposta)


class ABarraInvertidaNaoChegaNaTela(unittest.TestCase):
    def test_a_contagem_de_pacientes_sai_sem_barra_literal(self):
        resposta = ESPACO["_operational_fallback_result"](
            "quantos pacientes ativos eu tenho",
            {"active_patients_count": 2, "patients_count": 2},
        )
        self.assertNotIn(chr(92) + "n", resposta)
        self.assertIn("- Total de pacientes no contexto atual: 2.", resposta)

    def test_sem_total_a_linha_simplesmente_nao_aparece(self):
        resposta = ESPACO["_operational_fallback_result"](
            "quantos pacientes ativos eu tenho", {"active_patients_count": 2}
        )
        self.assertNotIn("Total de pacientes", resposta)
        self.assertNotIn(chr(92) + "n", resposta)

    def test_nenhuma_resposta_do_explica_carrega_barra_literal(self):
        """A regra, e nao a ocorrencia (secao 2.8).

        Varre as f-strings de main.py atras de `\\\\n` — a forma que imprime a
        barra em vez de quebrar a linha.

        COMENTARIO NAO CONTA. O comentario que registra o defeito cita a linha
        antiga, com a barra dobrada, e e assim que ele deve continuar: proibir a
        sequencia no arquivo inteiro apagaria o registro junto com o defeito. A
        varredura e sobre CODIGO.
        """
        dobrada = re.escape(chr(92) * 2) + "n"
        suspeitas = [
            linha.strip()
            for linha in MAIN.splitlines()
            if not linha.strip().startswith("#")
            and (
                re.search(r'f"[^"]*' + dobrada, linha)
                or re.search(r"f'[^']*" + dobrada, linha)
            )
        ]
        self.assertEqual(suspeitas, [], "f-string imprimindo barra invertida literal")


class ACitacaoEDoIndice(unittest.TestCase):
    """Uma pergunta sobre ZCR saiu no painel assinada com "Davis e Mermelstein
    (1980), MFCC": a busca por similaridade trouxe o trecho do MFCC por
    vizinhanca de vocabulario, e o filtro so perguntava "parece cientifico",
    nunca "e sobre isto"."""

    def test_zcr_nao_e_citado_com_a_fonte_do_mfcc(self):
        fontes = explica_clinico.referencias_citadas("para que serve o ZCR")
        self.assertTrue(fontes)
        for fonte in fontes:
            self.assertNotIn("Mermelstein", fonte)
        self.assertIn("openSMILE", fontes[0])

    def test_mfcc_cita_mfcc(self):
        fontes = explica_clinico.referencias_citadas("explique o MFCC7")
        self.assertEqual(len(fontes), 1)
        self.assertIn("Mermelstein", fontes[0])

    def test_indice_proprio_do_froid_nao_empresta_citacao(self):
        # IPM, IDM, zonas, bandas e indices DNA sao composicoes proprias, sem
        # estudo publicado que as sustente. Vazio e a resposta certa.
        for pergunta in (
            "o que e IND. ESPECTRAL",
            "explique o IPM",
            "e o DNA FLOOD?",
            "como interpreto a Zona 12",
        ):
            with self.subTest(pergunta=pergunta):
                self.assertEqual(explica_clinico.referencias_citadas(pergunta), [])

    def test_a_zona_nao_pega_a_citacao_emprestada_da_face(self):
        """Eu mesmo cometi o defeito que este commit veio corrigir.

        Na primeira versao amarrei FACS a ZONAS. Mas a zona e uma particao
        PROPRIA do espectro vocal — doze bandas log-espacadas de 65,4 a 1975,5
        Hz, com desvio contra a linha de base do paciente. O que FACS sustenta e
        a codificacao das AUs, que entra na zona apenas como o multiplicador
        2,5 quando ha dissonancia facial confirmada. Citar FACS sob uma
        pergunta sobre zona e exatamente emprestar a citacao do vizinho.

        DISSO. fica com FACS: ali a medida E a contagem de dissonancias faciais.
        """
        self.assertEqual(explica_clinico.INDICE_POR_ROTULO["ZONAS"].referencias, ())
        self.assertIn(
            "FACS", explica_clinico.INDICE_POR_ROTULO["DISSO."].referencias[0]
        )

    def test_as_fontes_sao_as_mesmas_do_acervo_do_servidor(self):
        """Espelho de nome (secao 2.9): a citacao escrita com texto proprio
        viraria uma segunda versao da mesma fonte."""
        rotulos = set(re.findall(r'"(Referencia cientifica: [^"]+)"', MAIN))
        for indice in explica_clinico.CATALOGO:
            for referencia in indice.referencias:
                with self.subTest(rotulo=indice.rotulo):
                    self.assertIn(referencia, rotulos)

    def test_o_endpoint_prefere_a_ficha_a_similaridade(self):
        corpo = _fatia(
            "async def _query_froid_knowledge(", "SQL_FORBIDDEN_RE = re.compile("
        )
        self.assertIn("explica_clinico.referencias_citadas(payload.query_text)", corpo)


class ADescricaoSaiDoGlossario(unittest.TestCase):
    """A resposta sobre ZCR que "pareceu boa" descrevia a medida como
    "proporcao entre partes faladas e nao faladas" e sinal de "fala
    fragmentada". Nada disso e o que o codigo calcula: ZCR e a taxa de troca de
    sinal da forma de onda, e sobe com fricativas por razao fonetica.

    O modelo improvisou porque a instrucao nao o proibia de descrever uma
    metrica do FROID a partir de conhecimento geral."""

    def test_a_instrucao_manda_a_descricao_vir_da_ficha(self):
        instrucao = re.sub(r"\s+", " ", explica_clinico.instrucao())
        self.assertIn("SAI DO GLOSSARIO, NAO DA SUA MEMORIA", instrucao)

    def test_a_instrucao_nomeia_o_erro_observado(self):
        instrucao = re.sub(r"\s+", " ", explica_clinico.instrucao())
        self.assertIn("partes faladas e nao faladas", instrucao)

    def test_a_ficha_do_zcr_diz_o_que_o_codigo_faz(self):
        ficha = explica_clinico.INDICE_POR_ROTULO["ZCR"]
        self.assertIn("troca de sinal", ficha.medida)
        self.assertIn("Fricativas", ficha.leitura)


if __name__ == "__main__":
    unittest.main()
