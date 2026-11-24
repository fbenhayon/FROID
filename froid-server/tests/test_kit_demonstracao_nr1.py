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
        self.assertNotIn("createElement('a')", JS)
        self.assertIn("aviso.textContent = corpo.mensagem", JS)

    def test_o_link_e_individual_e_so_o_hash_fica_no_banco(self):
        entrega = _funcao(MAIN, "_entregar_kit_nr1")
        self.assertIn("secrets.token_urlsafe(32)", entrega)
        self.assertIn("token_sha256=_hash_do_token_do_kit(token)", entrega)
        self.assertIn("KIT_NR1_ROTA + token", entrega)
        registro = _funcao(STORE, "registrar_link_do_kit")
        self.assertIn("kit_expira_em=now() + make_interval(days => %s)", registro)

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
        dias = _constante("KIT_NR1_VALIDADE_DIAS")
        self.assertIn(f"válido por {dias} dias", PAGINA)

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
        tupla = re.search(r"\(nome, email, empresa, cargo, contexto, origem, telefone\),", corpo)
        self.assertIsNotNone(tupla)
        self.assertEqual(len(colunas.split(",")), valores.count("%s"))
        self.assertEqual(len(colunas.split(",")), 7)

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
        self.assertIn("f\"{situacao}\\n\\n\"", corpo)
        self.assertLess(corpo.index('"FROID — Kit de demonstração NR-1"'),
                        corpo.index("[Site FROID] Kit NR-1 pedido por"))


class OKitSoNasceDoPilotoSimulado(unittest.TestCase):
    def test_o_gerador_recusa_dossie_que_nao_e_do_piloto(self):
        gerador = (REPO / "tools" / "gerar-kit-demonstracao-nr1.py").read_text(encoding="utf-8")
        self.assertIn('if "DADOS SIMULADOS" not in nome_org:', gerador)
        self.assertIn("DADOS SIMULADOS — documento demonstrativo, sem validade documental", gerador)


if __name__ == "__main__":
    unittest.main()
