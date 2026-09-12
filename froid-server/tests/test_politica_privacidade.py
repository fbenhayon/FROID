"""Os documentos juridicos tem de contar a MESMA historia, e a historia do codigo.

Este arquivo nasceu em 12/09/2026, de duas descobertas que so aparecem quando se
confrontam os documentos uns com os outros e com a fonte:

  A ESTONIA NUNCA EXISTIU. Oito paginas do site, em quatro idiomas, publicavam
  "hospedagem na Estonia". A Hetzner nao opera datacenter na Estonia. Pior: havia
  um TESTE exigindo a frase — `assertIn("hospedagem na Estônia")` —, de modo que
  a correcao seria reprovada pela suite. E o playbook interno da casa ja citava
  "estar hospedado na Estonia" como FALACIA de conformidade automatica com o
  RGPD: o pais errado ja vinha com o argumento errado de brinde.

  OS TERMOS DIZIAM QUE O FROID GRAVA. A secao "Gravacao, audio e video" obrigava
  o profissional a colher consentimento "para gravacao" e a evitar "gravacoes
  clandestinas" — deveres reais, de uma funcionalidade que NAO EXISTE. O
  contrato novo afirmava o contrario na clausula 8.3, e os dois documentos
  vigentes se contradiziam.

A licao das duas e a mesma e esta no §2.7: o mesmo fato copiado em varios
lugares diverge em silencio. Aqui o fato nao e um numero, e uma AFIRMACAO — e
afirmacao divergente entre dois documentos assinados e a primeira coisa que a
outra parte cita.
"""

import ast
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import legal_documents  # noqa: E402

CATALOGO = legal_documents.public_legal_catalog()
DOCS = CATALOGO["documents"]
TODO_O_TEXTO = " ".join(
    secao["body"] for doc in DOCS.values() for secao in doc["sections"]
)


def _corpo(chave: str) -> str:
    return " ".join(secao["body"] for secao in DOCS[chave]["sections"])


def _secao(chave: str, numero: str) -> str:
    """Recorta uma secao numerada pelo proprio numero, e nao por posicao."""
    texto = _corpo(chave)
    inicio = texto.find(numero + ". ")
    if inicio < 0:
        raise AssertionError(f"secao {numero} nao encontrada em {chave}")
    familia, indice = numero.rsplit(".", 1)
    fim = texto.find(f"{familia}.{int(indice) + 1}. ", inicio)
    return texto[inicio:fim] if fim > 0 else texto[inicio:inicio + 2600]


class ADuasPoliticasParaDoisProdutos(unittest.TestCase):
    """A Politica unica descrevia, para a empresa, a captacao de outro produto."""

    def test_cada_produto_tem_a_sua(self):
        self.assertEqual(["professional", "organization", "patient"], DOCS["privacy"]["audiences"])
        self.assertEqual(["nr1_company"], DOCS["privacy_nr1"]["audiences"])

    def test_a_empresa_assina_a_politica_dela(self):
        chaves = legal_documents.required_document_keys("nr1_company")
        self.assertIn("privacy_nr1", chaves)
        self.assertNotIn("privacy", chaves)

    def test_o_profissional_e_a_clinica_assinam_a_do_psique(self):
        for conta in ("individual", "organization"):
            with self.subTest(conta=conta):
                chaves = legal_documents.required_document_keys(conta)
                self.assertIn("privacy", chaves)
                self.assertNotIn("privacy_nr1", chaves)

    def test_a_politica_do_NR1_declara_o_que_NAO_trata(self):
        """Declarar a ausencia e melhor que deixar o leitor inferir pelo silencio.

        O texto unico anterior afirmava que o servico trata voz, imagem, sinais
        faciais, metricas acusticas e transcricao. Para quem so abre campanha de
        avaliacao de risco psicossocial, isso e falso — e assustador.
        """
        tres_cinco = _secao("privacy_nr1", "3.5")
        for ausente in ("voz", "imagem", "expressão facial", "transcrição de fala", "prontuário"):
            with self.subTest(categoria=ausente):
                self.assertIn(ausente, tres_cinco)
        self.assertIn("NÃO trata", tres_cinco)

    def test_cada_politica_diz_que_a_outra_existe(self):
        """Documento que se cala sobre o limite do proprio alcance convida o erro."""
        self.assertIn("FROID NR-1", _secao("privacy", "1.4"))
        self.assertIn("Política de Privacidade própria", _secao("privacy", "1.4"))
        self.assertIn("FROID Psique", _secao("privacy_nr1", "1.3"))


class NenhumDocumentoAfirmaQueOFroidGrava(unittest.TestCase):
    """A trava que confronta os documentos entre si.

    O contrato dizia que nao grava; os Termos regulavam a gravacao. Os dois
    vigentes ao mesmo tempo, e nenhum teste olhava para os dois juntos.
    """

    PROIBIDAS = (
        "funcionalidade de gravação",
        "autorização para gravação",
        "finalidade da gravação",
        "consentimento do paciente para gravação",
        "gravações clandestinas",
    )

    def test_nenhum_documento_do_catalogo_regula_uma_gravacao_inexistente(self):
        achados = []
        for chave, doc in DOCS.items():
            corpo = " ".join(s["body"] for s in doc["sections"])
            for frase in self.PROIBIDAS:
                if frase in corpo:
                    achados.append(f"{chave}: {frase!r}")
        self.assertEqual([], achados, "documento regulando gravacao inexistente: " + str(achados))

    def test_os_tres_documentos_do_psique_afirmam_a_ausencia_de_gravacao(self):
        """Contrato, Termos e TCLE, cada um na linguagem do seu leitor."""
        self.assertIn("não grava a sessão em áudio ou vídeo", _corpo("psique_contract"))
        self.assertIn("não grava a sessão em áudio ou vídeo", _corpo("terms"))
        # O TCLE fala com a pessoa atendida, e comeca por ali.
        self.assertIn("A sessão não é gravada.", _corpo("patient_tcle"))

    def test_o_site_tambem_parou_de_dizer_que_grava(self):
        """O site e o documento que o comprador le ANTES de assinar qualquer um."""
        for prefixo, frase in (
            ("", "não grava a sessão em áudio ou vídeo"),
            ("en/", "does not record the session in audio or video"),
            ("es/", "no graba la sesión en audio ni en video"),
            ("fr/", "n'enregistre pas la séance en audio ni en vidéo"),
        ):
            caminho = ROOT / "froid-site" / prefixo / "termos.html"
            with self.subTest(idioma=prefixo or "pt"):
                self.assertIn(frase, caminho.read_text(encoding="utf-8"))


class AEstoniaNaoVolta(unittest.TestCase):
    """Espelho de afirmacao: um pais errado copiado em dez lugares.

    A varredura e por GLOB, e nao por lista: pagina nova que herdar a frase de
    outra cai aqui sem ninguem precisar lembrar de incluir o arquivo.
    """

    def test_o_pais_desmentido_sumiu_do_catalogo_e_do_site(self):
        achados = []
        alvos = [SERVER_DIR / "legal_documents.py"]
        alvos += sorted((ROOT / "froid-site").rglob("*.html"))
        for caminho in alvos:
            texto = caminho.read_text(encoding="utf-8", errors="ignore")
            for grafia in ("Estônia", "Estonia", "Estonie"):
                if grafia in texto:
                    achados.append(f"{caminho.relative_to(ROOT).as_posix()}: {grafia}")
        self.assertEqual([], achados, "o pais desmentido voltou:\n  " + "\n  ".join(achados))

    def test_o_pais_apurado_esta_nos_dois_documentos_e_no_site(self):
        self.assertIn("Alemanha", _corpo("privacy"))
        self.assertIn("Alemanha", _corpo("privacy_nr1"))
        self.assertIn("Alemanha", _corpo("psique_contract"))
        for prefixo, frase in (
            ("", "na Alemanha"),
            ("en/", "in Germany"),
            ("es/", "en Alemania"),
            ("fr/", "en Allemagne"),
        ):
            caminho = ROOT / "froid-site" / prefixo / "privacidade.html"
            with self.subTest(idioma=prefixo or "pt"):
                self.assertIn(frase, caminho.read_text(encoding="utf-8"))


class OsSuboperadoresBatemComOCodigo(unittest.TestCase):
    """Fornecedor declarado tem de ser fornecedor que o codigo de fato chama."""

    MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
    COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    def test_a_transcricao_e_da_OpenAI_no_documento_e_no_codigo(self):
        self.assertIn('OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL"', self.MAIN)
        self.assertIn("OpenAI", _secao("privacy", "13.3"))

    def test_a_IA_de_apoio_nomeia_os_dois_provedores_que_o_codigo_usa(self):
        self.assertIn('FROID_EXPLICA_MODEL = os.getenv("FROID_EXPLICA_MODEL"', self.MAIN)
        self.assertIn("GEMINI_API_KEY", self.MAIN)
        self.assertIn("OPENAI_API_KEY", self.MAIN)
        treze_quatro = _secao("privacy", "13.4")
        self.assertIn("OpenAI", treze_quatro)
        self.assertIn("Google", treze_quatro)

    def test_a_retransmissao_e_NOSSA_e_nao_entra_como_suboperador(self):
        """O TURN e um conteiner do nosso compose, e nao um terceiro.

        O texto anterior dizia "podem utilizar servidor TURN", que o leitor so
        podia entender como mais um fornecedor recebendo a sessao. Declarar
        terceiro que nao existe e tao ruim quanto esconder um que existe.
        """
        self.assertIn("coturn/coturn", self.COMPOSE)
        treze_oito = _secao("privacy", "13.8")
        self.assertIn("operada pelo próprio FROID", treze_oito)
        self.assertIn("não constitui fornecedor externo", treze_oito)

    def test_onde_nao_houve_apuracao_o_documento_declara_a_ausencia(self):
        """Regra 1.1 da casa, aplicada a pratica de terceiro.

        Nao sabemos quanto tempo a OpenAI retem os segmentos. Escrever um prazo
        seria inventar; calar deixaria o leitor supor que nao ha retencao.
        """
        for secao in ("13.3", "13.4"):
            with self.subTest(secao=secao):
                self.assertIn("não apurad", _secao("privacy", secao))
        self.assertIn("não afirma a existência de decisão de adequação", _secao("privacy", "14.4"))


class APoliticaFalaAMesmaLinguaDoContrato(unittest.TestCase):
    """Onde os dois documentos tratam do mesmo fato, tem de dizer o mesmo."""

    def test_os_noventa_dias_sao_os_mesmos_nos_dois_e_no_codigo(self):
        dias = None
        for no in ast.parse((SERVER_DIR / "main.py").read_text(encoding="utf-8")).body:
            if isinstance(no, ast.Assign) and any(
                getattr(a, "id", "") == "LEITURA_APOS_ENCERRAMENTO_DIAS" for a in no.targets
            ):
                dias = no.value.value
        self.assertEqual(90, dias)
        self.assertIn("90 (noventa) dias", _secao("privacy", "15.7"))
        self.assertIn("90 (noventa) dias", _corpo("psique_contract"))

    def test_o_acervo_tem_as_mesmas_quatro_exclusoes_nos_dois(self):
        exclusoes = (
            "áudio bruto da pessoa atendida",
            "vídeo ou imagem de sua face",
            "identificadores pessoais diretos",
            "transcrição literal de sua fala",
        )
        dezesseis = _secao("privacy", "16.3")
        for excluido in exclusoes:
            with self.subTest(excluido=excluido):
                self.assertIn(excluido, dezesseis)
        # No contrato as mesmas quatro, com a pessoa atendida em caixa alta.
        contrato = _corpo("psique_contract")
        self.assertIn("áudio bruto da PESSOA ATENDIDA", contrato)
        self.assertIn("transcrição literal de sua fala", contrato)

    def test_a_fala_desidentificada_do_profissional_esta_nos_dois(self):
        self.assertIn("fala do profissional em forma desidentificada", _secao("privacy", "16.2"))
        self.assertIn("fala do PROFISSIONAL em forma desidentificada", _corpo("psique_contract"))

    def test_quem_le_prontuario_dentro_da_clinica_esta_nos_dois(self):
        """A 14.3 do contrato e a 18.3 da Politica descrevem a mesma politica de RLS."""
        dezoito = _secao("privacy", "18.3")
        self.assertIn("proprietário, administrador e supervisor", dezoito)
        self.assertIn("independentemente de haver vínculo de atendimento", dezoito)
        self.assertIn("independentemente de haver vínculo de atendimento", _corpo("psique_contract"))

    def test_os_tres_segundos_estao_nos_dois_e_no_codigo(self):
        core = (SERVER_DIR / "froid_core.py").read_text(encoding="utf-8")
        self.assertIn("keep_seconds: float = 3.0", core.replace("\n", " ").replace("  ", " "))
        self.assertIn("aproximadamente 3 (três) segundos", _secao("privacy", "6.1"))
        self.assertIn("aproximadamente 3 (três) segundos", _corpo("psique_contract"))

    def test_a_representacao_vocal_e_descrita_igual_nos_dois(self):
        nove = _secao("privacy", "9.3")
        self.assertIn("armazenamento local do navegador", nove)
        self.assertIn("não é transmitida ao FROID", nove)
        self.assertIn("não constrói representação numérica da voz da pessoa atendida",
                      _secao("privacy", "9.5"))


class APoliticaNaoCarregaLacunaNemPII(unittest.TestCase):
    """Documento versionado e com hash nao publica lacuna nem PII em codigo."""

    def test_nenhum_documento_tem_placeholder(self):
        for lacuna in ("[PREENCHER]", "[VALIDAR", "[●]", "[Nome completo"):
            with self.subTest(lacuna=lacuna):
                self.assertNotIn(lacuna, TODO_O_TEXTO)

    def test_o_canal_de_privacidade_e_renderizado_e_nao_escrito(self):
        fonte = (SERVER_DIR / "legal_documents.py").read_text(encoding="utf-8")
        self.assertIn("{supplier_privacy_email}", fonte)
        self.assertIn("supplier_privacy_email=", fonte)
        self.assertNotIn("050.983.408-61", fonte)

    def test_a_ausencia_de_encarregado_e_declarada_e_nao_omitida(self):
        """Canal apresentado como se houvesse designacao seria informacao falsa."""
        for chave, secao in (("privacy", "25.2"), ("privacy_nr1", "10.5")):
            with self.subTest(documento=chave):
                texto = _secao(chave, secao)
                self.assertIn("não designou formalmente encarregado", texto)
                self.assertIn("2/2022", texto)


if __name__ == "__main__":
    unittest.main()
