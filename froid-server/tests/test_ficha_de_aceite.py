"""A troca dos documentos jurídicos de 11/09/2026, e a ficha que ela exigiu.

O dono determinou a substituição integral de dois documentos do catálogo: o
TCLE da pessoa atendida e o contrato do FROID NR-1. Junto veio uma decisão de
desenho que este arquivo existe para guardar.

**O corpo do documento é idêntico para todos.** A identificação individual —
pessoa atendida, profissional, categoria e registro profissional, clínica,
data, versão, hash e identificador do aceite — NÃO entra no texto. Ela é
produzida ao lado, do cadastro, e viaja na ficha de aceite.

A razão é probatória e não estética: interpolar nome e CRP dentro do corpo daria
um sha256 diferente para cada pessoa, e `legal_acceptance_events` deixaria de
comparar aceites entre si. Perderíamos exatamente a prova que a tabela existe
para dar.

E a regra que atravessa tudo: **onde o cadastro não tem o dado, a ficha declara
a ausência.** Em nenhuma hipótese se apresenta o hash do texto de hoje como se
fosse o que a pessoa aceitou — esse vem do ledger, ou não vem.
"""

import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
PAINEL = SERVER_DIR.parent / "froid-dashboard" / "src"


def _corpo_da_funcao(fonte: str, nome: str) -> str:
    """O texto de uma função, isolado — para não acusar match de outro trecho."""
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return ast.get_source_segment(fonte, no) or ""
    raise AssertionError(f"funcao {nome} nao encontrada")


def _catalogo():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "legal_documents_ficha", SERVER_DIR / "legal_documents.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    implantacao = {
        "FROID_LEGAL_SUPPLIER_NAME": "Fornecedor de Teste",
        "FROID_LEGAL_SUPPLIER_TAX_ID": "documento-de-teste",
        "FROID_LEGAL_SUPPLIER_ADDRESS": "endereço-de-teste",
        "FROID_LEGAL_CONTACT_EMAIL": "contato@example.invalid",
        "FROID_LEGAL_PRIVACY_EMAIL": "privacidade@example.invalid",
    }
    with patch.dict(os.environ, implantacao):
        return modulo, modulo.public_legal_catalog()


class OTermoNovoDizOQueOSistemaFaz(unittest.TestCase):
    """As afirmações do TCLE conferidas contra o comportamento apurado no código.

    Não é revisão de redação. Cada asserção aqui corresponde a uma verificação
    feita no código em 11/09/2026, e está no teste porque uma frase jurídica que
    descreve comportamento inexistente é pior que frase nenhuma: quem lê acredita
    nela, e é ela que a parte adversa cita.
    """

    def setUp(self):
        self.modulo, self.catalogo = _catalogo()
        self.tcle = self.catalogo["documents"]["patient_tcle"]
        self.secoes = {s["heading"]: s["body"] for s in self.tcle["sections"]}

    def test_o_termo_e_da_pessoa_atendida_e_tem_as_vinte_e_duas_secoes(self):
        self.assertEqual(self.tcle["audiences"], ["patient"])
        self.assertEqual(len(self.tcle["sections"]), 22)
        self.assertEqual(len(self.tcle["sha256"]), 64)

    def test_a_sessao_nao_e_gravada_e_o_termo_diz_isso_sem_rodeio(self):
        """Apurado: nao existe uma unica escrita de arquivo de audio ou video no
        servidor. A unica ocorrencia de `.webm` no Python e o NOME passado a API
        de transcricao."""
        secao = self.secoes["4. Sua sessão não é gravada em áudio ou vídeo"]
        self.assertIn("não grava a sessão em áudio ou vídeo", secao)
        self.assertIn("não conserva um arquivo da sessão", secao)
        self.assertIn("não cria nem conserva uma gravação em vídeo", secao)

    def test_a_face_e_processada_no_dispositivo_e_a_imagem_nao_sobe(self):
        """Apurado: `froid-face.ts` roda o detector no navegador do paciente e o
        corpo da requisicao leva `blendshapes` e `invite`, mais nada. O endpoint
        `/facial-aus` nao tem campo de imagem."""
        secao = self.secoes["5. Como a expressão facial é processada"]
        self.assertIn("no próprio dispositivo da pessoa atendida", secao)
        self.assertIn("não é encaminhada ao servidor aplicativo", secao)
        self.assertIn("dados numéricos derivados", secao)
        # E a contrapartida: nao ha assinatura facial do paciente.
        self.assertIn("Não é criada assinatura facial", secao)

    def test_o_audio_tem_dois_caminhos_e_o_termo_separa_os_dois(self):
        """Apurado: janelas de ~1s alimentam um buffer rolante de 3s em memoria
        (froid_core.ingest_pcm, keep_seconds=3.0); segmentos de 7s vao a
        provedor externo para a transcricao. Sao rotas distintas, com destinos
        distintos, e a minuta anterior nao as distinguia."""
        secao = self.secoes["6. Como o áudio é processado"]
        self.assertIn("6.1. Medidas derivadas da voz", secao)
        self.assertIn("6.2. Transcrição", secao)
        self.assertIn("processados temporariamente", secao)
        # O terceiro e declarado, e nao escondido atras de "infraestrutura".
        self.assertIn("fornecedor tecnológico especializado em transcrição", secao)
        self.assertIn("não conserva esses segmentos como arquivos de áudio", secao)

    def test_a_transcricao_e_declarada_como_preservada_e_cifrada(self):
        """Apurado: `_save_session_reports` cifra a transcricao com Fernet e
        recusa gravar sem a chave. Preservar e verdade; dizer que nao preserva
        seria o defeito oposto."""
        secao = self.secoes["7. O que pode ficar guardado depois da sessão"]
        self.assertIn("a transcrição textual daquilo que foi falado", secao)
        self.assertIn("criptografia em repouso", secao)
        # O prazo e o do prontuario, e nao um numero que o FROID invente.
        self.assertIn(
            "obrigações legais, éticas e profissionais aplicáveis ao profissional",
            secao,
        )

    def test_a_fronteira_clinica_continua_inviolavel_no_texto(self):
        """A regra da casa: nenhum texto pode sugerir que o empregador le dado
        clinico individual."""
        secao = self.secoes["12. Se o FROID for disponibilizado por seu empregador"]
        for vedado in (
            "conteúdo das sessões",
            "transcrições das conversas",
            "indicadores clínicos individuais",
            "diagnóstico ou informação clínica individual",
        ):
            with self.subTest(item=vedado):
                self.assertIn(vedado, secao)
        self.assertIn("constituem serviços distintos", secao)

    def test_o_termo_nao_promete_gravacao_que_o_produto_nao_tem(self):
        """O defeito que esta troca corrigiu.

        Os Termos de Uso definiam a plataforma como podendo "incluir gravação" e
        dedicavam uma secao inteira ao dever do profissional "ao utilizar
        funcionalidade de gravação". Essa funcionalidade nao existe. O TCLE novo
        nao repete o erro, e este teste guarda isso.
        """
        todas = " ".join(s["body"] for s in self.tcle["sections"])
        self.assertNotIn("funcionalidade de gravação", todas)
        self.assertNotIn("gravação da sessão pelo profissional", todas)

    def test_a_identificacao_nao_entra_no_corpo_do_termo(self):
        """O item 21 descreve a ficha; ele NAO carrega linhas em branco.

        Campo vazio dentro de documento juridico convida alguem a preencher a
        mao, e ai existem duas versoes do mesmo Termo — uma com o hash que o
        aceite prova, outra com o que a pessoa assinou de caneta.
        """
        secao = self.secoes["21. Identificação do atendimento"]
        self.assertIn("registrada pelo FROID no ato do aceite", secao)
        self.assertIn("a partir dos dados de cadastro", secao)
        self.assertIn("identificador eletrônico do aceite", secao)
        self.assertIn("é idêntico para todas as pessoas atendidas", secao)
        todas = " ".join(s["body"] for s in self.tcle["sections"])
        self.assertNotIn("_____", todas)
        self.assertNotIn("[preencher]", todas)
        self.assertNotIn("[●]", todas)

    def test_o_contato_do_fornecedor_vem_da_configuracao_e_nao_do_codigo(self):
        """A minuta trazia "froid@froid.com.br" escrito no corpo.

        Endereco de contato do fornecedor e configuracao de implantacao, pela
        mesma razao do CPF: uma copia no codigo diverge da outra em silencio, e
        o proprio arquivo ja tem teste travando que a PII do fornecedor nao seja
        commitada.
        """
        fonte = (SERVER_DIR / "legal_documents.py").read_text(encoding="utf-8")
        self.assertIn("supplier_contact_email=", fonte)
        self.assertIn("supplier_privacy_email=", fonte)
        # A verificacao que importa e sobre o TEXTO RENDERIZADO, e nao sobre o
        # arquivo: o endereco real aparece no comentario que conta por que ele
        # saiu do corpo, e comentario nao vai para documento nenhum.
        todas = " ".join(s["body"] for s in self.tcle["sections"])
        self.assertNotIn("froid@froid.com.br", todas)
        contatos = self.secoes["22. Contatos"]
        self.assertIn("contato@example.invalid", contatos)
        self.assertIn("privacidade@example.invalid", contatos)


class OContratoDoNr1NaoVazaDadoDeUmCliente(unittest.TestCase):
    """A minuta enviada trazia a qualificação de UMA contratante e o CPF do dono.

    O contrato do catálogo é o texto que TODA empresa NR-1 aceita. Nome de
    cliente, CPF, endereço e marcas de revisão comercial dentro dele iriam para
    a tela de aceite de todo mundo.
    """

    def setUp(self):
        self.modulo, self.catalogo = _catalogo()
        self.contrato = self.catalogo["documents"]["nr1_company_contract"]
        self.todas = " ".join(s["body"] for s in self.contrato["sections"])

    def test_nenhum_dado_de_cliente_ou_do_dono_ficou_no_texto(self):
        for vazamento in (
            "TATICCA",
            "050.983.408",
            "Roque Petrella",
            "FÁBIO DE ASSUMPÇÃO BENHAYON",
            "PENDÊNCIA PARA FECHAMENTO",
        ):
            with self.subTest(item=vazamento):
                self.assertNotIn(vazamento, self.todas)

    def test_o_fornecedor_entra_pela_configuracao_de_implantacao(self):
        partes = {s["heading"]: s["body"] for s in self.contrato["sections"]}["Partes"]
        self.assertIn("Fornecedor de Teste", partes)
        self.assertIn("documento-de-teste", partes)
        # E a contratante e referida pelo cadastro, nao nomeada no texto.
        self.assertIn("identificada pela razão social, pelo CNPJ e pela sede", partes)
        self.assertIn("constantes do cadastro", partes)

    def test_a_qualificacao_das_partes_saiu_para_a_ficha(self):
        fecho = {s["heading"]: s["body"] for s in self.contrato["sections"]}[
            "Aceite eletrônico e identificação das Partes"
        ]
        self.assertIn("registrada pelo FROID no ato do aceite", fecho)
        self.assertIn("é idêntico para todas as contratantes", fecho)
        self.assertNotIn("_____", self.todas)
        self.assertNotIn("[●]", self.todas)


class AFichaDeAceiteDeclaraAAusencia(unittest.TestCase):
    """A ficha nunca preenche o que o cadastro não tem, e nunca inventa o hash."""

    def test_campo_sem_cadastro_sai_declarado_e_nunca_em_branco(self):
        corpo = _corpo_da_funcao(MAIN, "_ficha_valor")
        self.assertIn("FICHA_NAO_REGISTRADO", corpo)
        self.assertIn('FICHA_NAO_REGISTRADO = "não registrado"', MAIN)

    def test_o_hash_vem_do_ledger_e_nunca_do_catalogo_de_hoje(self):
        """O erro que este teste impede é silencioso e grave.

        Recalcular o sha256 a partir do catálogo vigente faria um aceite de
        versão anterior "provar" um documento que a pessoa nunca viu. O hash sai
        do ledger append-only, ou sai declarado ausente.
        """
        corpo = _corpo_da_funcao(MAIN, "_ficha_de_aceite_do_paciente")
        self.assertIn('aceite.get("document_sha256")', corpo)
        # Nenhuma leitura do catalogo vigente dentro do produtor da ficha.
        self.assertNotIn("public_legal_catalog", corpo)

    def test_a_organizacao_da_ficha_usa_a_regra_canonica(self):
        """Minha primeira versao procurava `profile["organization_id"]`.

        A chave nao existe: organizacao e DERIVADA (CNPJ para clinica e empresa,
        e-mail para o autonomo) e a regra mora em `organization_id_for_profile`.
        A busca casaria zero perfis e a ficha sairia inteira em "nao registrado"
        sem nada acusando o erro — o defeito que so aparece quando alguem pede o
        comprovante.
        """
        corpo = _corpo_da_funcao(MAIN, "_ficha_de_aceite_da_organizacao")
        self.assertIn("tenant_organization_id_for_profile(", corpo)
        self.assertNotIn('candidato.get("organization_id")', corpo)

    def test_a_ficha_do_paciente_carrega_os_campos_do_item_21(self):
        corpo = _corpo_da_funcao(MAIN, "_ficha_de_aceite_do_paciente")
        for campo in (
            "pessoa_atendida",
            "data_e_hora_do_aceite",
            "versao_do_termo",
            "hash_da_versao",
            "identificador_eletronico_do_aceite",
        ):
            with self.subTest(campo=campo):
                self.assertIn(f'"{campo}"', corpo)
        # Categoria, registro e clinica chegam pelo produtor do profissional.
        profissional = _corpo_da_funcao(MAIN, "_ficha_do_profissional")
        for campo in (
            "profissional_responsavel",
            "categoria_profissional",
            "registro_profissional",
            "clinica_ou_organizacao",
        ):
            with self.subTest(campo=campo):
                self.assertIn(f'"{campo}"', profissional)

    def test_categoria_e_registro_saem_do_cadastro_do_servidor(self):
        """E nao da copia que o gerador de PDF le no `localStorage`.

        Os dois campos existem no cadastro (`professionalCouncil` e
        `professionalRegistry` em `profile_fields`). A copia no navegador serve
        ao documento impresso; a prova do aceite le do servidor.
        """
        corpo = _corpo_da_funcao(MAIN, "_ficha_do_profissional")
        self.assertIn('campos.get("professionalCouncil")', corpo)
        self.assertIn('campos.get("professionalRegistry")', corpo)
        # A leitura e do cadastro do servidor. O `localStorage` so aparece no
        # docstring, que e onde a distincao entre as duas copias esta explicada.
        self.assertIn("PROFESSIONAL_PROFILES.get(owner_email)", corpo)

    def test_a_ficha_da_organizacao_declara_o_que_ninguem_coletou(self):
        """Sede, cargo, local do aceite e testemunhas não são perguntados hoje.

        Sair em branco num documento jurídico se lê como "não havia". O que há é
        "não perguntamos", e é isso que a ficha diz.
        """
        corpo = _corpo_da_funcao(MAIN, "_ficha_de_aceite_da_organizacao")
        for campo in ("sede", "cargo", "local_do_aceite"):
            with self.subTest(campo=campo):
                self.assertIn(f'"{campo}": FICHA_NAO_REGISTRADO', corpo)

    def test_o_identificador_do_aceite_sai_do_ledger(self):
        """A coluna `id` sempre existiu e nunca saía da leitura.

        Sem ela, a ficha teria de inventar um identificador para cumprir o item
        21 — que é exatamente o que não se faz nesta casa.
        """
        corpo = _corpo_da_funcao(STORE, "list_legal_acceptances")
        self.assertIn("subject_kind, id", corpo)
        self.assertIn('"acceptance_id"', corpo)

    def test_existe_rota_para_a_pessoa_atendida_ler_a_propria_ficha(self):
        self.assertIn('@app.get("/api/patient-portal/legal-acceptance")', MAIN)
        corpo = _corpo_da_funcao(MAIN, "patient_portal_legal_acceptance")
        self.assertIn("_require_current_patient(request)", corpo)
        self.assertIn("_ficha_de_aceite_do_paciente(patient)", corpo)
        # A comparacao com o texto vigente sai pronta, e nao delegada a tela.
        self.assertIn("matches_current_version", corpo)

    def test_a_rota_da_organizacao_devolve_a_ficha_do_contrato(self):
        corpo = _corpo_da_funcao(MAIN, "list_organization_legal_acceptances")
        self.assertIn("_ficha_de_aceite_da_organizacao(", corpo)
        self.assertIn("nr1_company_contract", corpo)


class APesquisaViroUmaEscolhaDeVerdade(unittest.TestCase):
    """O item 17 do TCLE oferece SIM e NÃO. Até 11/09/2026 nada coletava isso.

    A tela de convite montava o payload sem `research_anonymized`, e o campo
    chegava ao servidor sempre no default. O documento prometia uma escolha que
    a tela não apresentava — o padrão de defeito desta casa, agora num
    documento que a pessoa assina.
    """

    def setUp(self):
        self.convite = (PAINEL / "pages" / "PatientInvitePage.tsx").read_text(
            encoding="utf-8"
        )

    def test_a_tela_envia_a_escolha_de_pesquisa(self):
        self.assertIn("research_anonymized: consent.research_anonymized", self.convite)

    def test_a_faculdade_nao_e_arrastada_pelo_consentimento_unico(self):
        """O clique das obrigatorias nao pode marcar a opcional junto.

        Autorizacao por arraste nao e autorizacao, e o proprio item 14 do Termo
        manda apresentar finalidade nao necessaria separadamente.
        """
        self.assertNotIn("research_anonymized: consentAll", self.convite)

    def test_a_caixa_da_pesquisa_nasce_desmarcada(self):
        self.assertIn("research_anonymized: false", self.convite)
        self.assertIn('updateConsent("research_anonymized", event.target.checked)', self.convite)

    def test_a_tela_diz_que_recusar_nao_afeta_o_atendimento(self):
        self.assertIn("recusar não afeta o atendimento", self.convite)


class TodaTelaJuridicaPreservaAQuebraDeLinha(unittest.TestCase):
    """As alíneas do contrato novo vivem em linhas próprias.

    Uma das três telas que exibem documento jurídico não preservava a quebra, e
    era justamente a tela em que a empresa ACEITA: as nove alíneas da cláusula
    15.4 sairiam emendadas num parágrafo só.
    """

    TELAS = (
        ("LegalPages.tsx", "section.body"),
        ("Nr1Acceptance.tsx", "secao.body"),
        ("Nr1CompanyOnboarding.tsx", "secao.body"),
    )

    def test_as_tres_telas_usam_whitespace_pre_line(self):
        for nome, _ in self.TELAS:
            with self.subTest(tela=nome):
                fonte = (PAINEL / "pages" / nome).read_text(encoding="utf-8")
                self.assertIn("whitespace-pre-line", fonte)


if __name__ == "__main__":
    unittest.main()
