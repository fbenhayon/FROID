"""Kit de demonstração NR-1: formulário do site -> lead gravado -> link individual por e-mail.

Determinação do dono, 23/11/2026: o visitante preenche um cadastro curto na
página NR-1 e recebe o PDF; os dados ficam guardados para o comercial ligar.
Cada teste abaixo afirma uma garantia dessa cadeia, não o mecanismo.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
SITE = REPO / "froid-site-dev"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
JS = (SITE / "site-assets" / "kit-nr1.js").read_text(encoding="utf-8")
PAGINA = (SITE / "nr1" / "apresentacao-nr1.html").read_text(encoding="utf-8")


def _constante(nome: str) -> str:
    for no in ast.parse(MAIN).body:
        if isinstance(no, ast.Assign) and any(
            isinstance(alvo, ast.Name) and alvo.id == nome for alvo in no.targets
        ):
            return ast.literal_eval(no.value)
    raise AssertionError(f"{nome} não está definido em main.py")


def _funcao(fonte: str, nome: str) -> str:
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return ast.get_source_segment(fonte, no)
    raise AssertionError(f"{nome} não existe")


class OKitSoSaiPorCadastroEPorEmail(unittest.TestCase):
    """Determinação do dono, 23/11/2026: só por e-mail, link individual que expira.

    Substitui OLinkApontaParaUmArquivoQueExiste, que exigia o PDF em
    froid-site-dev — exatamente o endereço público que permitia baixar o kit
    sem cadastro. A decisão foi revogada; o teste guarda a nova.
    """

    def test_o_pdf_existe_dentro_do_backend(self):
        arquivo = SERVER_DIR / "assets" / "froid-kit-demonstracao-nr1.pdf"
        self.assertTrue(arquivo.is_file(), f"{arquivo} não existe: o link entregaria 503")
        self.assertGreater(arquivo.stat().st_size, 100_000)
        self.assertTrue(arquivo.read_bytes().startswith(b"%PDF"))
        self.assertIn('"assets" / "froid-kit-demonstracao-nr1.pdf"', MAIN)

    def test_nenhum_pdf_do_kit_no_site_publico(self):
        for site in ("froid-site-dev", "froid-site"):
            achados = list((REPO / site).rglob("*kit*nr1*.pdf"))
            with self.subTest(site=site):
                self.assertEqual(achados, [], "o kit voltaria a ser baixável sem cadastro")

    def test_a_resposta_do_cadastro_nao_traz_link(self):
        corpo = _funcao(MAIN, "register_nr1_lead")
        self.assertNotIn("kit_url", corpo)
        self.assertNotIn("KIT_NR1_ROTA", corpo)

    def test_a_tela_nao_monta_link_nenhum(self):
        self.assertNotIn(".pdf", JS)
        self.assertNotIn("kit_url", JS)
        self.assertNotIn("/api/kit-nr1", JS)
        self.assertNotIn("/api/proposta-nr1", JS)
        # O único link que a tela monta é a frase do sumário, que leva à
        # janela do formulário (24/11/2026), nunca ao kit.
        self.assertEqual(JS.count("createElement('a')"), 1)
        self.assertEqual(re.findall(r"\.href = '([^']*)'", JS), ["apresentacao-nr1.html#pedir-kit"])
        self.assertIn("aviso.textContent = corpo.mensagem", JS)

    def test_o_link_e_individual_e_so_o_hash_fica_no_banco(self):
        entrega = _funcao(MAIN, "_entregar_kit_nr1")
        self.assertIn("secrets.token_urlsafe(32)", entrega)
        self.assertIn("token_sha256=_hash_do_token_do_kit(token)", entrega)
        self.assertIn("KIT_NR1_ROTA + token", entrega)
        registro = _funcao(STORE, "registrar_link_do_kit")
        self.assertIn("kit_expira_em=now() + make_interval(hours => %s)", registro)

    def test_link_vencido_e_desconhecido_tem_respostas_distintas(self):
        abrir = _funcao(STORE, "abrir_link_do_kit")
        self.assertIn("kit_expira_em > now()", abrir)
        for situacao in ('"valido"', '"expirado"', '"inexistente"'):
            with self.subTest(situacao=situacao):
                self.assertIn(situacao, abrir)
        rota = _funcao(MAIN, "baixar_kit_nr1")
        for codigo in ("status_code=410", "status_code=404", "status_code=503"):
            with self.subTest(codigo=codigo):
                self.assertIn(codigo, rota)
        self.assertIn('"Cache-Control": "private, no-store"', rota)

    def test_a_validade_tem_uma_fonte_e_a_pagina_concorda(self):
        # Regra 2.7: a página escreve o número; o teste confere contra a fonte.
        # 24/11/2026, decisão do dono: a validade passou de 7 dias para 24 horas.
        horas = _constante("KIT_NR1_VALIDADE_HORAS")
        self.assertEqual(horas, 24)
        self.assertIn(f"valem por {horas} horas", PAGINA)
        self.assertNotIn("KIT_NR1_VALIDADE_DIAS", MAIN)

    def test_a_migracao_do_link_existe(self):
        sql = (SERVER_DIR / "migrations" / "057_marketing_leads_link_do_kit.sql").read_text(encoding="utf-8")
        for coluna in ("kit_token_sha256", "kit_expira_em", "kit_acessos", "kit_ultimo_acesso_em"):
            with self.subTest(coluna=coluna):
                self.assertIn(f"ADD COLUMN IF NOT EXISTS {coluna}", sql)
        self.assertIn("'057_marketing_leads_link_do_kit'", sql)

    def test_o_comercial_le_se_o_kit_foi_aberto(self):
        # Padrão 2.1: colunas novas sem leitor não dizem nada a ninguém.
        exportador = (SERVER_DIR / "tools" / "exportar_leads.py").read_text(encoding="utf-8")
        listagem = _funcao(STORE, "list_marketing_leads")
        for coluna in ("kit_expira_em", "kit_acessos", "kit_ultimo_acesso_em"):
            with self.subTest(coluna=coluna):
                self.assertIn(f'"{coluna}"', exportador)
                self.assertIn(coluna, listagem)


class OFormularioChegaAoEndpointCerto(unittest.TestCase):
    def test_a_origem_do_site_e_a_que_o_servidor_reconhece(self):
        origem = _constante("ORIGEM_KIT_NR1")
        self.assertIn(f"origem: '{origem}'", JS)

    def test_a_pagina_tem_o_formulario_e_carrega_o_script(self):
        self.assertIn('id="form-kit-nr1"', PAGINA)
        self.assertIn('action="/api/leads/nr1"', PAGINA)
        self.assertIn("site-assets/kit-nr1.js", PAGINA)

    def test_todo_campo_que_o_script_le_existe_no_formulario(self):
        lidos = set(re.findall(r"valor\('(\w+)'\)", JS))
        self.assertTrue(lidos)
        for campo in lidos:
            with self.subTest(campo=campo):
                self.assertIn(f'name="{campo}"', PAGINA)

    def test_os_quatro_idiomas_tem_a_janela_com_todos_os_campos(self):
        # 24/11/2026: a seção do kit virou um botão abaixo de cada seção, que
        # abre a janela do formulário, nos quatro idiomas (decisão do dono).
        lidos = set(re.findall(r"valor\('(\w+)'\)", JS))
        self.assertTrue({"cnpj", "estabelecimentos", "trabalhadores", "empresa"} <= lidos)
        for idioma, pasta in (("pt", ""), ("en", "en/"), ("fr", "fr/"), ("es", "es/")):
            pagina = (SITE / pasta / "nr1" / "apresentacao-nr1.html").read_text(encoding="utf-8")
            with self.subTest(idioma=idioma):
                self.assertIn(f'data-idioma="{idioma}"', pagina)
                self.assertIn("site-assets/kit-nr1.js", pagina)
                self.assertIn("site-assets/kit-nr1.css", pagina)
                self.assertNotIn('id="kit-demonstracao"', pagina)
                for campo in lidos:
                    self.assertIn(f'name="{campo}"', pagina)
                # O sumário da página nasce de todo <h2> (navigation.js): a
                # janela não pode ter um, senão vira "seção".
                janela = pagina[pagina.index('id="dialogo-kit-nr1"'):pagina.index("</dialog>")]
                self.assertNotIn("<h2", janela)

    def test_a_frase_do_kit_esta_no_sumario_de_todas_as_paginas_nr1(self):
        # 24/11/2026, pedido do dono: sem botão no fim de cada seção; uma frase
        # âmbar, sem contorno, no sumário de links do topo, em toda página NR-1.
        self.assertNotIn("kit-gatilho", JS)
        self.assertIn("document.querySelector('.page-outline')", JS)
        self.assertIn("'apresentacao-nr1.html#pedir-kit'", JS)
        for idioma in ("pt", "en", "fr", "es"):
            self.assertRegex(JS, rf"\n    {idioma}: '[^']+'", idioma)
        self.assertIn("Receba o material GRO, a AEP, a classificação dos fatores, o inventário de riscos "
                      "e o plano de ação que a organização apresenta numa fiscalização, com dados simulados "
                      "e sem validade documental", JS)
        paginas = [p for p in SITE.glob("**/nr1/*.html")
                   if 'http-equiv="refresh"' not in p.read_text(encoding="utf-8")]
        self.assertEqual(len(paginas), 16)
        for p in paginas:
            texto = p.read_text(encoding="utf-8")
            with self.subTest(pagina=str(p.relative_to(SITE))):
                self.assertIn("site-assets/kit-nr1.js", texto)
                self.assertIn("site-assets/kit-nr1.css", texto)
                # depois de navigation.js, que monta o sumário
                self.assertLess(texto.index('site-assets/navigation.js?v='), texto.index('site-assets/kit-nr1.js?v='))

    def test_resposta_sem_mensagem_e_falha_visivel(self):
        self.assertIn("if (!corpo.mensagem) { falhou(0); return; }", JS)


class OLeadFicaGuardadoComTudoQueOComercialPrecisa(unittest.TestCase):
    def test_o_endpoint_grava_o_telefone(self):
        corpo = _funcao(MAIN, "register_nr1_lead")
        self.assertIn('"telefone": _texto("telefone", 40)', corpo)
        self.assertIn("register_marketing_lead(**lead)", corpo)

    def test_insert_tem_colunas_placeholders_e_valores_em_igual_numero(self):
        # O teste real contra PostgreSQL é pulado sem banco; este lê o INSERT
        # (skill-froid-master, seção 3: "onde o teste real é pulado, escreva o estático").
        corpo = _funcao(STORE, "register_marketing_lead")
        colunas = re.search(r"INSERT INTO marketing_leads \"\s*\"\(([^)]*)\)", corpo).group(1)
        valores = re.search(r"VALUES \(([^)]*)\)", corpo).group(1)
        tupla = re.search(r"\(nome, email, empresa, cargo, contexto, origem, telefone,\s*"
                          r"cnpj, estabelecimentos, trabalhadores\),", corpo)
        self.assertIsNotNone(tupla)
        self.assertEqual(len(colunas.split(",")), valores.count("%s"))
        self.assertEqual(len(colunas.split(",")), 10)

    def test_a_migracao_do_telefone_existe(self):
        sql = (SERVER_DIR / "migrations" / "056_marketing_leads_telefone.sql").read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN IF NOT EXISTS telefone", sql)
        self.assertIn("'056_marketing_leads_telefone'", sql)

    def test_alguem_le_a_tabela(self):
        # Até 23/11/2026 marketing_leads gravava e nada lia (padrão 2.1).
        exportador = (SERVER_DIR / "tools" / "exportar_leads.py").read_text(encoding="utf-8")
        self.assertIn("list_marketing_leads()", exportador)
        self.assertIn("opt_out_at", exportador)


class AFalhaDeEmailNaoPerdeOLeadNemFicaMuda(unittest.TestCase):
    def test_o_lead_e_gravado_antes_de_qualquer_envio(self):
        corpo = _funcao(MAIN, "register_nr1_lead")
        self.assertLess(corpo.index("register_marketing_lead"), corpo.index("_entregar_kit_nr1"))

    def test_cada_falha_de_envio_registra_o_motivo(self):
        corpo = _funcao(MAIN, "_entregar_kit_nr1")
        for evento in (
            "froid.kit_nr1_mailer_disabled",
            "froid.kit_nr1_link_store_failed",
            "froid.kit_nr1_link_without_lead",
            "froid.kit_nr1_team_notice_failed",
            "froid.kit_nr1_visitor_send_failed",
        ):
            with self.subTest(evento=evento):
                self.assertIn(evento, corpo)

    def test_a_tela_so_diz_que_mandou_email_quando_mandou(self):
        corpo = _funcao(MAIN, "register_nr1_lead")
        self.assertIn('"email_enviado": enviado_ao_visitante', corpo)
        self.assertNotIn("O material chega no seu e-mail", corpo)
        # Equipe avisada é afirmada só quando o aviso saiu de fato.
        self.assertIn("elif equipe_avisada:", corpo)

    def test_a_equipe_sabe_se_o_kit_chegou_ao_visitante(self):
        corpo = _funcao(MAIN, "_entregar_kit_nr1")
        self.assertIn("f\"{situacao}\\n{situacao_proposta}\\n\\n\"", corpo)
        self.assertLess(corpo.index('"FROID — Kit de demonstração e proposta NR-1"'),
                        corpo.index("[Site FROID] Kit NR-1 pedido por"))


class APropostaVemCalculadaParaOCliente(unittest.TestCase):
    """Pedido do dono, 24/11/2026: o e-mail do kit leva também a proposta, já
    com os dados da empresa e o valor mensal calculado pela tabela vigente."""

    @classmethod
    def setUpClass(cls):
        from datetime import datetime, timezone
        import pricing_nr1
        import proposta_nr1
        cls.pricing = pricing_nr1
        cls.proposta = proposta_nr1
        cls.lead = {
            "nome": "Responsável Exemplo", "cargo": "RH", "email": "rh@exemplo.com.br",
            "empresa": "Empresa Exemplo Ltda", "cnpj": "00000000000191",
            "estabelecimentos": 1, "trabalhadores": 300,
        }
        cls.retrato = proposta_nr1.montar_retrato(
            lead=cls.lead, lead_id="3f9a1c22-0000-4000-8000-000000000000",
            tabela=pricing_nr1.TABELA_VIGENTE, procedencia="modulo",
            emitida_em=datetime(2026, 11, 24, tzinfo=timezone.utc),
        )
        cls.fonte = (SERVER_DIR / "proposta_nr1.py").read_text(encoding="utf-8")

    def test_o_valor_e_o_do_motor_de_preco(self):
        # Regra 2.7: o total da proposta é o do simulador, centavo por centavo.
        calculo = self.pricing.simular(300, 1, self.pricing.TABELA_VIGENTE)
        self.assertEqual(self.retrato["mensal"], self.pricing.formatar_brl(calculo["monthlyTotalCents"]))
        self.assertEqual(self.retrato["tabela"]["sha256"], calculo["pricingTable"]["sha256"])

    def test_nenhum_preco_ou_piso_escrito_no_texto(self):
        self.assertNotRegex(self.fonte, r"R\$\s*\d")
        self.assertIn("nr1_compliance.MIN_COHORT_CUT", self.fonte)
        self.assertIn("nr1_compliance.MIN_COHORT_TOTAL", self.fonte)

    def test_a_pagina_traz_os_dados_do_cliente_e_a_gratuidade(self):
        pagina = self.proposta.renderizar(self.retrato)
        for trecho in ("Empresa Exemplo Ltda", "00.000.000/0001-91", "Responsável Exemplo",
                       self.retrato["mensal"], self.retrato["numero"],
                       "Sem custo até a entrega do primeiro relatório"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, pagina)

    def test_a_proposta_nao_pede_dado_pessoal_de_trabalhador(self):
        pagina = self.proposta.renderizar(self.retrato)
        self.assertIn("Não envie ao FROID nome, CPF, e-mail, telefone", pagina)
        self.assertIn("<b>matrícula</b> e <b>setor</b>", pagina)

    def test_empresa_abaixo_do_piso_e_avisada(self):
        from datetime import datetime, timezone
        pequeno = dict(self.lead, trabalhadores=12)
        retrato = self.proposta.montar_retrato(
            lead=pequeno, lead_id="aa", tabela=self.pricing.TABELA_VIGENTE,
            procedencia="modulo", emitida_em=datetime(2026, 11, 24, tzinfo=timezone.utc))
        self.assertIn("não alcança o mínimo", self.proposta.renderizar(retrato))

    def test_cnpj_numerico_e_alfanumerico(self):
        n = self.proposta.normalizar_cnpj
        self.assertEqual(n("00.000.000/0001-91"), "00000000000191")
        self.assertIsNone(n("00.000.000/0001-92"))
        self.assertIsNone(n("11.111.111/1111-11"))
        # Exemplo publicado pela Receita para o CNPJ alfanumérico (julho/2026).
        self.assertEqual(n("12.ABC.345/01DE-35"), "12ABC34501DE35")

    def test_o_cadastro_do_kit_exige_os_tres_campos_e_diz_qual_faltou(self):
        corpo = _funcao(MAIN, "register_nr1_lead")
        for trecho in ("CNPJ inválido", "número de estabelecimentos", "número de trabalhadores"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, corpo)
        self.assertLess(corpo.index("normalizar_cnpj"), corpo.index("register_marketing_lead"))

    def test_o_mesmo_link_abre_a_proposta_com_respostas_distintas(self):
        rota = _funcao(MAIN, "abrir_proposta_nr1")
        for codigo in ("status_code=410", "status_code=404", "status_code=503", '"sem_proposta"'):
            with self.subTest(codigo=codigo):
                self.assertIn(codigo, rota)
        entrega = _funcao(MAIN, "_entregar_kit_nr1")
        self.assertIn("PROPOSTA_NR1_ROTA + token", entrega)
        self.assertIn("proposta=retrato", entrega)
        abrir = _funcao(STORE, "abrir_proposta")
        self.assertIn("kit_expira_em > now()", abrir)

    def test_proposta_nao_calculada_e_avisada_a_equipe(self):
        entrega = _funcao(MAIN, "_entregar_kit_nr1")
        self.assertIn("ATENÇÃO: a proposta NÃO foi calculada", entrega)

    def test_a_migracao_e_o_leitor_do_comercial(self):
        sql = (SERVER_DIR / "migrations" / "058_marketing_leads_proposta.sql").read_text(encoding="utf-8")
        exportador = (SERVER_DIR / "tools" / "exportar_leads.py").read_text(encoding="utf-8")
        for coluna in ("cnpj", "estabelecimentos", "trabalhadores", "proposta_acessos"):
            with self.subTest(coluna=coluna):
                self.assertIn(f"ADD COLUMN IF NOT EXISTS {coluna}", sql)
                self.assertIn(f'"{coluna}"', exportador)
        self.assertIn("'058_marketing_leads_proposta'", sql)


class OKitSoNasceDoPilotoSimulado(unittest.TestCase):
    def test_o_gerador_recusa_dossie_que_nao_e_do_piloto(self):
        gerador = (REPO / "tools" / "gerar-kit-demonstracao-nr1.py").read_text(encoding="utf-8")
        self.assertIn('if "DADOS SIMULADOS" not in nome_org:', gerador)
        self.assertIn("DADOS SIMULADOS — documento demonstrativo, sem validade documental", gerador)

    def test_o_link_da_capa_e_o_do_formulario(self):
        # Regra 2.7: o kit impresso aponta para a janela do formulário; se o
        # endereço mudar num lugar e não no outro, o PDF leva a lugar nenhum.
        gerador = (REPO / "tools" / "gerar-kit-demonstracao-nr1.py").read_text(encoding="utf-8")
        caminho = _constante("KIT_NR1_PAGINA_DO_FORMULARIO")
        self.assertIn(f'URL_DO_PEDIDO = "https://www.froid.com.br{caminho}"', gerador)
        self.assertIn("Sem custo até a entrega do primeiro relatório", gerador)


if __name__ == "__main__":
    unittest.main()
