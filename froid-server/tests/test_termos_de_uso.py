"""Os Termos de Uso, a numeracao do acervo e a terminologia unificada.

Este arquivo guarda tres decisoes do dono de 12/09/2026 e as TRES correcoes que
o rascunho dele nao podia carregar para producao.

AS CORRECOES. O texto enviado trazia, sem que isso fosse intencional, as mesmas
duas afirmacoes falsas que ja tinham sido corrigidas no contrato dias antes —
porque o rascunho fora escrito antes daquela apuracao:

  13   listava cinco capacidades de obtencao de registros como obrigacao, entre
       elas exportacao em lote e em formato estruturado. Nao existem. O proprio
       rascunho trazia uma nota de "condicao para publicacao" reconhecendo isso.

  15.3 dizia que ser proprietario, socio, administrador ou gestor NAO confere
       acesso ao conteudo clinico. E a mesma frase que a clausula 14.3 do
       contrato carregava: a politica de RLS da migration 007 concede owner,
       administrator e supervisor SEM vinculo de atendimento.

  25.1 listava um "Anexo de Tratamento e Protecao de Dados" e um "Anexo Tecnico
       de Suboperadores" como documentos separados. Eles nao existem: sao os
       Anexos I e II DO CONTRATO. Clausula de precedencia que lista documento
       inexistente e convite para alguem exigi-lo.

A licao vale alem destes Termos: documento juridico escrito antes de uma
apuracao carrega a versao antiga dos fatos, e a unica defesa e confrontar cada
afirmacao com o codigo de novo, toda vez.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import legal_documents  # noqa: E402

DOCS = legal_documents.public_legal_catalog()["documents"]


def _corpo(chave: str) -> str:
    return " ".join(s["body"] for s in DOCS[chave]["sections"])


def _clausula(chave: str, numero: str) -> str:
    texto = _corpo(chave)
    inicio = texto.find(numero + ". ")
    if inicio < 0:
        raise AssertionError(f"clausula {numero} nao encontrada em {chave}")
    familia, indice = numero.rsplit(".", 1)
    fim = texto.find(f"{familia}.{int(indice) + 1}. ", inicio)
    return texto[inicio:fim] if fim > 0 else texto[inicio:inicio + 3000]


class OsTermosDescrevemOQueExiste(unittest.TestCase):
    """A clausula 13 nao promete exportacao que o produto nao tem."""

    def test_o_que_a_plataforma_oferece_esta_descrito(self):
        treze = _clausula("terms", "13.2")
        for capacidade in (
            "listagem das sessões",
            "transcrição textual integral com marcação dos interlocutores",
            "emissão de documento descritivo da sessão",
        ):
            with self.subTest(capacidade=capacidade):
                self.assertIn(capacidade, treze)

    def test_as_tres_ausencias_estao_declaradas(self):
        treze = _clausula("terms", "13.3")
        self.assertIn("não inclui a transcrição textual integral", treze)
        self.assertIn("não existe função de exportação em lote", treze)
        self.assertIn("não existe função de exportação dos registros em formato estruturado", treze)

    def test_os_termos_e_o_contrato_declaram_as_MESMAS_ausencias(self):
        """Dois documentos vigentes que descrevem a mesma funcionalidade tem de
        descreve-la igual. Divergir e dar a outra parte a escolha do texto."""
        for frase in (
            "não existe função de exportação em lote",
            "não existe função de exportação dos registros em formato estruturado",
        ):
            with self.subTest(frase=frase):
                self.assertIn(frase, _corpo("psique_contract"))
                self.assertIn(frase, _corpo("terms"))

    def test_a_janela_de_noventa_dias_e_a_mesma_nos_dois(self):
        self.assertIn("90 (noventa) dias", _clausula("terms", "13.5"))
        self.assertIn("independe de comunicação do FROID", _clausula("terms", "13.6"))
        self.assertIn("não assume obrigação de aviso prévio", _clausula("terms", "13.6"))


class OsTermosDizemAVerdadeSobreQuemLeOProntuario(unittest.TestCase):
    """A 15.3 do rascunho afirmava o oposto do que a politica de RLS executa."""

    def test_a_clausula_declara_o_acesso_administrativo_que_existe(self):
        quinze = _clausula("terms", "15.3")
        self.assertIn("proprietário, administrador e supervisor", quinze)
        self.assertIn("independentemente de haver vínculo de atendimento", quinze)

    def test_a_frase_falsa_do_rascunho_nao_esta_no_documento(self):
        corpo = _corpo("terms")
        self.assertNotIn("não confere automaticamente acesso ao conteúdo clínico", corpo)

    def test_a_capacidade_tecnica_nao_e_vendida_como_autorizacao(self):
        self.assertIn("não constitui autorização ética ou legal", _clausula("terms", "15.4"))

    def test_os_tres_documentos_descrevem_o_mesmo_acesso(self):
        """Contrato 14.3, Politica 18.3 e Termos 15.3 falam do mesmo fato."""
        frase = "independentemente de haver vínculo de atendimento"
        for chave in ("psique_contract", "privacy", "terms"):
            with self.subTest(documento=chave):
                self.assertIn(frase, _corpo(chave))


class ACadeiaDocumentalEstaHarmonizada(unittest.TestCase):
    """Ordem canonica do dono: Contrato -> Termos -> Politica -> TCLE -> Anexos -> SLA."""

    def test_a_precedencia_lista_apenas_documentos_que_existem(self):
        vinte_e_cinco = _clausula("terms", "25.1")
        # Os anexos sao DO CONTRATO, e nao documentos soltos.
        self.assertIn("Anexo I", vinte_e_cinco)
        self.assertIn("Anexo II", vinte_e_cinco)
        self.assertNotIn("Anexo de Tratamento e Proteção de Dados", _corpo("terms"))
        self.assertNotIn("Anexo Técnico de Suboperadores", _corpo("terms"))

    def test_a_ordem_canonica_aparece_no_contrato_e_nos_termos(self):
        for chave, numero in (("psique_contract", "1.8"), ("terms", "25.1")):
            with self.subTest(documento=chave):
                texto = _clausula(chave, numero)
                posicoes = [
                    texto.find(nome)
                    for nome in ("Contrato", "Termos de Uso", "Política de Privacidade",
                                 "Termo de Ciência e Consentimento Informado")
                ]
                self.assertTrue(all(p >= 0 for p in posicoes), texto[:400])
                self.assertEqual(sorted(posicoes), posicoes, "a ordem canonica mudou")

    def test_nenhum_documento_se_apresenta_como_substituto_dos_outros(self):
        frase = "nenhum substitui os demais"
        for chave in ("psique_contract", "terms"):
            with self.subTest(documento=chave):
                self.assertIn(frase, _corpo(chave))

    def test_a_politica_e_citada_pelo_nome_que_ela_tem(self):
        """Ela virou duas em 12/09/2026; citar 'a Política de Privacidade do
        FROID' mandaria o leitor procurar um documento que nao existe mais."""
        for chave in ("psique_contract", "terms"):
            with self.subTest(documento=chave):
                self.assertIn("Política de Privacidade — FROID Psique", _corpo(chave))
                self.assertNotIn("Política de Privacidade do FROID", _corpo(chave))


class ARedacaoSobreIAFicaComoOCFPRecomenda(unittest.TestCase):
    """A IA auxilia; o profissional interpreta, revisa e decide."""

    def test_a_clausula_nomeia_os_riscos_que_o_CFP_aponta(self):
        dez = _clausula("terms", "10.7")
        for risco in ("erro", "excesso de confiança", "discriminação", "dados sensíveis"):
            with self.subTest(risco=risco):
                self.assertIn(risco, dez)
        self.assertIn("não possui julgamento ético próprio", dez)

    def test_a_revisao_humana_e_obrigacao_e_nao_sugestao(self):
        self.assertIn("deverá revisar", _clausula("terms", "7.2"))
        self.assertIn("antes da incorporação", _clausula("terms", "7.3"))

    def test_a_fronteira_do_SATEPSI_esta_declarada(self):
        self.assertIn("SATEPSI", _clausula("terms", "6.4"))


class ONumeroDaClausulaViveNoTextoEnaoNaTela(unittest.TestCase):
    """O painel ja numerava por POSICAO ao renderizar; o texto nao carregava numero.

    E o texto armazenado que o hash cobre e que o acervo do FROID Explica cita
    entre aspas. "Clausula 8.3" e conferivel por quem le; "a oitava secao"
    depende de o leitor contar — e a contagem muda quando uma secao entra.
    """

    NUMERADOS = ("psique_contract", "terms", "terms_nr1", "privacy", "privacy_nr1",
                 "nr1_company_contract")

    def test_todo_documento_estrutural_tem_titulos_numerados(self):
        for chave in self.NUMERADOS:
            with self.subTest(documento=chave):
                titulos = [s["heading"] for s in DOCS[chave]["sections"]]
                sem_numero = [t for t in titulos if not re.match(r"^\d+(\.\d+)*\.\s", t)
                              and not t.startswith("Anexo")]
                self.assertEqual([], sem_numero, f"titulos sem numero em {chave}: {sem_numero}")

    def test_a_numeracao_e_sequencial_e_sem_buraco(self):
        for chave in self.NUMERADOS:
            with self.subTest(documento=chave):
                numeros = [
                    int(m.group(1))
                    for s in DOCS[chave]["sections"]
                    if (m := re.match(r"^(\d+)\.\s", s["heading"]))
                ]
                self.assertEqual(list(range(1, len(numeros) + 1)), numeros)


class ATerminologiaEUmaSoNosDocumentos(unittest.TestCase):
    """PESSOA ATENDIDA nos documentos juridicos. Decisao do dono.

    A excecao e o "Portal do Paciente", que e NOME de uma area existente no
    produto. Trocar o nome no documento e manter na tela mandaria o leitor
    procurar uma area que nao existe com aquele nome — o §2.9 outra vez.
    """

    def test_os_documentos_usam_pessoa_atendida(self):
        achados = []
        for chave, doc in DOCS.items():
            texto = " ".join(s["body"] for s in doc["sections"]) + " " + doc["title"]
            for m in re.finditer(r"[Pp]acientes?", texto):
                trecho = texto[max(0, m.start() - 18): m.end()]
                if "Portal do Paciente" in texto[max(0, m.start() - 17): m.end() + 1]:
                    continue
                achados.append(f"{chave}: ...{trecho}")
        self.assertEqual(
            [], achados, "'paciente' fora do nome da area: " + " | ".join(achados)
        )

    def test_o_nome_da_area_do_produto_continua_como_esta(self):
        """Ele existe na tela, e o documento tem de mandar para o lugar certo."""
        self.assertIn("Portal do Paciente", _corpo("privacy"))
        rotas = (ROOT / "froid-dashboard" / "src" / "App.tsx").read_text(encoding="utf-8")
        self.assertIn('path="/paciente"', rotas)


if __name__ == "__main__":
    unittest.main()
