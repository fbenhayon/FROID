"""Kit de demonstração NR-1: formulário do site -> lead gravado -> link do PDF.

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


class OLinkApontaParaUmArquivoQueExiste(unittest.TestCase):
    def test_o_pdf_publicado_existe_no_site(self):
        caminho = _constante("KIT_NR1_CAMINHO")
        arquivo = SITE / caminho.lstrip("/")
        self.assertTrue(arquivo.is_file(), f"{arquivo} não existe: o link entregaria 404")
        self.assertGreater(arquivo.stat().st_size, 100_000)
        self.assertTrue(arquivo.read_bytes().startswith(b"%PDF"))

    def test_o_site_nao_escreve_o_caminho_do_pdf(self):
        # Uma fonte só (regra 2.7): o caminho vem na resposta do servidor.
        self.assertNotIn(".pdf", JS)
        self.assertIn("corpo.kit_url", JS)


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

    def test_link_ausente_na_resposta_e_falha_visivel(self):
        self.assertIn("if (!corpo.kit_url) { falhou(0); return; }", JS)


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
            "froid.kit_nr1_team_notice_failed",
            "froid.kit_nr1_visitor_send_failed",
        ):
            with self.subTest(evento=evento):
                self.assertIn(evento, corpo)

    def test_a_tela_so_diz_que_mandou_email_quando_mandou(self):
        corpo = _funcao(MAIN, "register_nr1_lead")
        self.assertIn('"email_enviado": enviado_ao_visitante', corpo)
        self.assertNotIn("O material chega no seu e-mail", corpo)


class OKitSoNasceDoPilotoSimulado(unittest.TestCase):
    def test_o_gerador_recusa_dossie_que_nao_e_do_piloto(self):
        gerador = (REPO / "tools" / "gerar-kit-demonstracao-nr1.py").read_text(encoding="utf-8")
        self.assertIn('if "DADOS SIMULADOS" not in nome_org:', gerador)
        self.assertIn("DADOS SIMULADOS — documento demonstrativo, sem validade documental", gerador)


if __name__ == "__main__":
    unittest.main()
