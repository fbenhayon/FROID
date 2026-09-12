"""O contrato do FROID Psique tem de continuar dizendo a verdade sobre o codigo.

Este arquivo existe porque tres clausulas do rascunho de 12/09/2026 afirmavam
coisas que o produto NAO fazia — e nenhuma delas era detectavel por leitura:

  9     dizia que a atribuicao de fala usava assinatura vocal do PROFISSIONAL.
        Uma primeira apuracao concluiu que nao existia assinatura nenhuma e que
        tudo era prefixo de texto. Estava ERRADA: a assinatura existe, e o
        prefixo e a SAIDA dela. Contrato escrito sobre qualquer uma das duas
        leituras erradas descreveria um produto que nao e este.

  13.3  listava cinco capacidades de exportacao como obrigacao do servico.
        Duas nao existem: exportacao em lote por pessoa ou periodo, e
        exportacao em formato estruturado. Prometer no contrato o que o produto
        nao faz e a unica especie de defeito que ninguem descobre testando o
        produto — so descobre quem cobra a promessa.

  14.3  dizia que a condicao de proprietario, administrador ou gestor NAO
        concede acesso a conteudo clinico. A politica de RLS da migration 007
        concede: owner, administrator e supervisor leem `session_reports` da
        organizacao sem vinculo de atendimento. O contrato afirmava o oposto do
        que o banco executa.

A trava nao e sobre a redacao. E sobre a correspondencia entre a frase do
contrato e o comportamento do codigo: quando um dos dois mudar sem o outro,
este arquivo reprova e diz qual dos dois ficou para tras.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import legal_documents  # noqa: E402

CATALOGO = legal_documents.public_legal_catalog()
CONTRATO = CATALOGO["documents"]["psique_contract"]
TEXTO = " ".join(secao["body"] for secao in CONTRATO["sections"])
TITULOS = [secao["heading"] for secao in CONTRATO["sections"]]


def _clausula(numero: str) -> str:
    """O texto de UMA clausula numerada, recortado do corpo que a contem.

    Recorta pelo proprio numero e nao por posicao: clausula que muda de lugar
    continua sendo encontrada, e clausula que some faz o teste falhar em vez de
    devolver o vizinho.
    """
    inicio = TEXTO.find(numero + ". ")
    if inicio < 0:
        raise AssertionError(f"clausula {numero} nao encontrada no contrato")
    familia, indice = numero.rsplit(".", 1)
    seguinte = f"{familia}.{int(indice) + 1}. "
    fim = TEXTO.find(seguinte, inicio)
    return TEXTO[inicio:fim] if fim > 0 else TEXTO[inicio:inicio + 2600]


class UmContratoParaAsDuasContasClinicas(unittest.TestCase):
    """Eram dois textos que repetiam oito decimos um do outro, e ja divergiam."""

    def test_o_catalogo_tem_um_contrato_do_psique_e_nao_dois(self):
        self.assertIn("psique_contract", legal_documents.DOCUMENT_TEMPLATES)
        for aposentado in ("professional_contract", "organization_contract"):
            with self.subTest(aposentado=aposentado):
                self.assertNotIn(aposentado, legal_documents.DOCUMENT_TEMPLATES)

    def test_as_duas_contas_clinicas_assinam_o_mesmo_documento(self):
        for conta in ("individual", "professional", "organization"):
            with self.subTest(conta=conta):
                self.assertIn(
                    "psique_contract", legal_documents.required_document_keys(conta)
                )

    def test_a_empresa_do_NR1_continua_fora(self):
        """Fronteira que a unificacao nao pode derrubar por descuido."""
        chaves = legal_documents.required_document_keys("nr1_company")
        self.assertNotIn("psique_contract", chaves)
        self.assertIn("nr1_company_contract", chaves)

    def test_a_audiencia_declarada_cobre_as_duas_contas(self):
        self.assertEqual(["professional", "organization"], CONTRATO["audiences"])

    def test_as_clausulas_de_pessoa_juridica_declaram_o_proprio_escopo(self):
        """Sem isto, o autonomo assinaria governanca de perfis que nao tem.

        Aceite de clausula inaplicavel nao protege ninguem: dilui o que e
        aplicavel e da a outra parte a primeira frase para dizer que o aceite
        foi generico.
        """
        self.assertIn(
            "aplicam-se apenas quando a CONTRATANTE for pessoa jurídica", _clausula("1.5")
        )
        self.assertIn("Quando a CONTRATANTE for pessoa jurídica", _clausula("14.1"))

    def test_o_documento_nao_carrega_lacuna_para_preencher_depois(self):
        """Placeholder em documento versionado e com hash e defeito, nao rascunho.

        O hash prova o texto exibido. Publicar "[PREENCHER]" congela a lacuna
        dentro da prova.
        """
        for lacuna in ("[PREENCHER]", "[VALIDAR", "[●]", "[ ]", "____"):
            with self.subTest(lacuna=lacuna):
                self.assertNotIn(lacuna, TEXTO)

    def test_a_qualificacao_do_fornecedor_e_renderizada_e_nao_escrita(self):
        """PII do fornecedor e configuracao de implantacao, nunca fonte."""
        fonte = (SERVER_DIR / "legal_documents.py").read_text(encoding="utf-8")
        self.assertIn("{supplier_identity}", fonte)
        self.assertNotIn("050.983.408-61", fonte)
        self.assertNotIn("FÁBIO DE ASSUMPÇÃO BENHAYON", fonte)


class AClausula9DescreveAAtribuicaoQueExiste(unittest.TestCase):
    """A assinatura vocal EXISTE, e a clausula precisa descrever a real.

    Mecanismo conferido em 12/09/2026 em `LiveSession.tsx`: no modo automatico,
    `buildVoiceSignature` monta um vetor de oito medidas agregadas do sinal a
    partir de ao menos 18 amostras da fala do PROFISSIONAL, com limiar derivado
    da dispersao das proprias amostras; `voiceDistance` compara cada trecho com
    esse vetor e o resultado e estabilizado por maioria. O vetor e gravado em
    `localStorage` sob `froid_dr_voiceprint_v1` e nunca sai do navegador.
    """

    LIVE = (ROOT / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx").read_text(
        encoding="utf-8"
    )

    def test_a_clausula_descreve_o_vetor_e_nao_promete_biometria(self):
        nove = _clausula("9.2") + _clausula("9.7")
        self.assertIn("não contém áudio", nove)
        self.assertIn("não permite reconstruir a fala", nove)
        self.assertIn("não constitui identificação biométrica", nove)

    def test_a_clausula_diz_que_o_vetor_nao_sai_do_navegador(self):
        self.assertIn("armazenamento local do navegador", _clausula("9.3"))
        self.assertIn("não é transmitida ao FORNECEDOR", _clausula("9.3"))

    def test_o_CODIGO_continua_guardando_o_vetor_so_no_navegador(self):
        """A trava de verdade: se o vetor comecar a ser enviado, isto reprova.

        A clausula 9.3 afirma que a representacao nao e transmitida ao
        FORNECEDOR. Enquanto a unica escrita for no `localStorage` e a variavel
        nao aparecer em corpo de requisicao, a afirmacao se sustenta.
        """
        self.assertIn('DR_VOICEPRINT_STORAGE_KEY = "froid_dr_voiceprint_v1"', self.LIVE)
        self.assertIn("window.localStorage.setItem(DR_VOICEPRINT_STORAGE_KEY", self.LIVE)
        # Nenhum corpo de requisicao carrega a assinatura.
        for envio in (
            "drVoiceSignature)",
            "drVoiceSignature,",
        ):
            for linha in self.LIVE.split("\n"):
                if envio in linha and ("body" in linha or "JSON.stringify" in linha):
                    self.fail(f"assinatura vocal indo para requisicao: {linha.strip()}")

    def test_o_servidor_nao_tem_assinatura_vocal_de_ninguem(self):
        fontes = " ".join(
            caminho.read_text(encoding="utf-8")
            for caminho in SERVER_DIR.glob("*.py")
        )
        for termo in ("voiceprint", "voice_embedding", "speaker_embedding"):
            with self.subTest(termo=termo):
                self.assertNotIn(termo, fontes)

    def test_a_pessoa_atendida_nao_ganha_assinatura_e_a_atribuicao_e_residual(self):
        """O que a 9.5 afirma e o que o codigo faz: PC e o que nao e DR."""
        self.assertIn(
            "não constrói representação numérica da voz da PESSOA ATENDIDA", _clausula("9.5")
        )
        self.assertIn("é residual", _clausula("9.5"))
        self.assertIn('distance <= currentSignature.threshold ? "DR" : "PC"', self.LIVE)

    def test_sem_modo_automatico_a_captacao_local_e_da_pessoa_atendida(self):
        self.assertIn("tratada como sendo da PESSOA ATENDIDA", _clausula("9.6"))
        self.assertIn(
            'const metricSpeaker = hasAutomaticVoiceGuard ? attributedSpeaker : "PC";',
            self.LIVE,
        )


class AClausula13DescreveOQueExisteEOQueNaoExiste(unittest.TestCase):
    """Prometer exportacao que nao existe e defeito que so o cliente descobre."""

    def test_o_que_a_plataforma_oferece_esta_descrito(self):
        treze = _clausula("13.3")
        for capacidade in (
            "listagem das sessões",
            "transcrição textual integral com marcação dos interlocutores",
            "emissão de documento descritivo da sessão",
        ):
            with self.subTest(capacidade=capacidade):
                self.assertIn(capacidade, treze)

    def test_as_tres_ausencias_estao_declaradas(self):
        quatro = _clausula("13.4")
        self.assertIn("não inclui a transcrição textual integral", quatro)
        self.assertIn("não existe função de exportação em lote", quatro)
        self.assertIn("não existe função de exportação dos registros em formato estruturado", quatro)

    def test_o_documento_impresso_REALMENTE_nao_traz_a_transcricao(self):
        """A ausencia declarada na 13.4(a) tem de continuar sendo ausencia.

        Se um dia a transcricao entrar no documento, a clausula passa a mentir
        por omissao — negando uma capacidade que o produto ganhou.
        """
        pdf = (ROOT / "froid-dashboard" / "src" / "lib" / "report-pdf.ts").read_text(
            encoding="utf-8"
        )
        arvore = pdf[pdf.index("export function buildProfessionalReport"):]
        arvore = arvore[: arvore.index("export function buildPatientReport")]
        self.assertNotIn("report.transcript", arvore)

    def test_nao_existe_rota_de_exportacao_do_profissional_no_servidor(self):
        """A unica rota de export do servidor e a do PACIENTE, pela LGPD."""
        main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        rotas = re.findall(r'@app\.(?:get|post)\("([^"]*export[^"]*)"', main)
        self.assertEqual(["/api/patient-portal/privacy/export"], rotas)


class AJanelaDeNoventaDiasEstaNoContratoENoCodigo(unittest.TestCase):
    """Numero copiado do codigo para o contrato precisa de fonte unica.

    O prazo da clausula 13.6 e o mesmo que o portao de assinatura aplica. Sem
    esta trava, alterar um dos dois deixaria o contrato prometendo uma janela e
    o servidor concedendo outra — e quem descobre e o profissional que perdeu o
    acesso antes do prazo prometido.
    """

    def test_o_contrato_promete_o_prazo_que_o_codigo_concede(self):
        main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        dias = None
        for no in ast.parse(main).body:
            if isinstance(no, ast.Assign) and any(
                getattr(alvo, "id", "") == "LEITURA_APOS_ENCERRAMENTO_DIAS"
                for alvo in no.targets
            ):
                dias = no.value.value
        self.assertEqual(90, dias, "a constante do portao mudou")
        self.assertIn(f"janela de {dias} (noventa) dias", _clausula("13.6"))

    def test_o_contrato_promete_leitura_com_plano_vencido(self):
        self.assertIn("não impede a leitura dos registros", _clausula("13.5"))

    def test_a_janela_nao_promete_alterar_nem_apagar(self):
        """O portao so abre GET; o contrato nao pode prometer mais que isso."""
        self.assertIn("bem como a alteração ou a exclusão", _clausula("13.7"))


class AClausula14DizAVerdadeSobreQuemLeOProntuario(unittest.TestCase):
    """O rascunho afirmava o OPOSTO do que a politica de RLS executa."""

    RLS = (
        SERVER_DIR / "migrations" / "007_multitenant_security_hardening.sql"
    ).read_text(encoding="utf-8")

    def test_a_clausula_declara_o_acesso_administrativo_que_existe(self):
        quatorze = _clausula("14.3")
        self.assertIn("proprietário, administrador e supervisor", quatorze)
        self.assertIn("independentemente de haver vínculo de atendimento", quatorze)

    def test_o_banco_CONCEDE_esse_acesso_e_por_isso_a_clausula_o_declara(self):
        politica = self.RLS[self.RLS.index("CREATE POLICY session_reports_read"):][:900]
        self.assertIn("'owner','administrator','supervisor'", politica.replace(" ", ""))

    def test_a_capacidade_tecnica_nao_e_vendida_como_autorizacao(self):
        self.assertIn("não constitui autorização ética ou legal", _clausula("14.4"))

    def test_a_fronteira_do_empregador_esta_no_contrato_e_no_codigo(self):
        import tenant_access

        self.assertIn("não recebem acesso a conteúdo clínico identificado", _clausula("14.5"))
        for papel in ("owner", "administrator", "supervisor", "auditor"):
            with self.subTest(papel=papel):
                self.assertIn(papel, tenant_access.EMPLOYER_SIDE_ROLES)
        # A autoatribuicao tambem e cortada, senao o empregador se atribuiria o
        # proprio empregado e leria pelo escopo de 'professional'.
        self.assertIn("assignments.manage", tenant_access.CLINICAL_IDENTIFIED_PERMISSIONS)
        self.assertIn("essa supressão alcança também a atribuição", _clausula("14.5"))


class AClausula19DeclaraOAcervoEAsQuatroExclusoes(unittest.TestCase):
    """O Data-FROID passa a ter finalidade declarada, e limites declarados."""

    def test_a_finalidade_real_esta_escrita(self):
        dezenove = _clausula("19.1")
        self.assertIn("Data-FROID", dezenove)
        self.assertIn("problemas de saúde mental", dezenove)

    def test_a_fala_desidentificada_do_profissional_integra_o_acervo(self):
        dois = _clausula("19.2")
        self.assertIn("fala do PROFISSIONAL em forma desidentificada", dois)
        self.assertIn("marcadores tipificados", dois)

    def test_as_quatro_exclusoes_continuam_de_pe(self):
        tres = _clausula("19.3")
        for excluido in (
            "áudio bruto da PESSOA ATENDIDA",
            "vídeo ou imagem de sua face",
            "identificadores pessoais diretos",
            "transcrição literal de sua fala",
        ):
            with self.subTest(excluido=excluido):
                self.assertIn(excluido, tres)

    def test_a_assimetria_e_dita_com_todas_as_letras(self):
        """Preservar a fala de um e nao a do outro precisa ser declarado.

        Decisao do dono: e condicao do servico, e nao escolha facultativa. Uma
        assimetria dessas, se nao for dita, e a primeira coisa que alguem aponta.
        """
        quatro = _clausula("19.4")
        self.assertIn("é deliberada", quatro)
        self.assertIn("condição do serviço", quatro)

    def test_o_descarte_por_ambiguidade_e_registrado_e_nao_silencioso(self):
        """Acervo vazio por recusa nao pode se confundir com acervo sem alimento."""
        self.assertIn("o descarte será registrado como tal", _clausula("19.5"))

    def test_o_CODIGO_continua_excluindo_a_fala_literal_do_paciente(self):
        deid = (SERVER_DIR / "froid_deidentify.py").read_text(encoding="utf-8")
        self.assertIn("DESIDENTIFICADO", deid)


class OsNumerosDoContratoBatemComOsDoProduto(unittest.TestCase):
    """Espelho de numero: o contrato copia valores que vivem no codigo."""

    def test_os_tres_segundos_da_janela_acustica(self):
        core = (SERVER_DIR / "froid_core.py").read_text(encoding="utf-8")
        assinatura = re.search(r"def ingest_pcm\([^)]*keep_seconds: float = ([0-9.]+)", core)
        self.assertIsNotNone(assinatura, "ingest_pcm mudou de assinatura")
        self.assertEqual(3.0, float(assinatura.group(1)))
        self.assertIn("aproximadamente 3 (três) segundos", _clausula("8.6"))

    def test_o_buffer_nao_e_persistido_e_o_contrato_afirma_isso(self):
        oito = _clausula("8.6")
        self.assertIn("não é gravado em disco", oito)
        self.assertIn("não integra backup", oito)
        core = (SERVER_DIR / "froid_core.py").read_text(encoding="utf-8")
        trecho = core[core.index("def ingest_pcm"):][:1200]
        for persistencia in ("json.dumps", "pickle", "asdict", "to_csv"):
            with self.subTest(persistencia=persistencia):
                self.assertNotIn(persistencia, trecho)

    def test_a_face_manda_numero_e_nao_imagem(self):
        """Conferido pelo parser: a assinatura estava quebrada em tres linhas.

        A primeira versao casava o texto literal `def process_facial_frame(...)`
        numa linha so, e reprovou por formatacao — sem que a garantia tivesse
        mudado. O que precisa ser verdade e que a porta de entrada da analise
        facial receba NUMERO, e nunca quadro de imagem.
        """
        facs = (SERVER_DIR / "froid_facs.py").read_text(encoding="utf-8")
        alvo = next(
            no for no in ast.parse(facs).body
            if isinstance(no, ast.FunctionDef) and no.name == "process_facial_frame"
        )
        parametros = [(a.arg, ast.unparse(a.annotation)) for a in alvo.args.args]
        self.assertEqual([("blendshapes", "Dict[str, float]")], parametros)
        self.assertIn("somente valores numéricos derivados", _clausula("8.4"))


class ATranscricaoNaoCaiParaTextoClaro(unittest.TestCase):
    """A 10.4 promete que a falta de chave NAO vira gravacao em texto claro."""

    def test_a_clausula_promete_falhar_em_vez_de_degradar(self):
        dez = _clausula("10.4")
        self.assertIn("não autorizará seu armazenamento persistente em texto claro", dez)
        self.assertIn("a operação falha e é registrada como falha", dez)

    def test_o_codigo_levanta_erro_em_vez_de_gravar_em_claro(self):
        store = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        self.assertIn("transcript_storage_locked", store + main)


if __name__ == "__main__":
    unittest.main()
