"""Auditoria de ponta a ponta do controle de acesso.

O que esta cadeia precisa garantir, e o que cada parte cobre:

  1. A restricao atinge UM alvo e nenhum outro.
  2. Quem teve acesso e perdeu recebe MENSAGEM, e nao tela vazia.
  3. Quem nunca teve organizacao — o profissional autonomo — continua entrando.
  4. O dado fica protegido mesmo com sessao ja aberta.
  5. Toda operacao e reversivel e nada e apagado.
  6. So administrador opera, e a operacao fica registrada.

O risco desta area e assimetrico. Falhar em bloquear e ruim; bloquear demais e
pior, porque derruba cliente pagante sem ninguem perceber a causa. Metade das
asserções abaixo existe para o segundo caso.
"""

from __future__ import annotations

import io
import os
import re
import sys

import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

MAIN = io.open(os.path.join(RAIZ, "main.py"), encoding="utf-8").read()
STORE = io.open(os.path.join(RAIZ, "tenant_store.py"), encoding="utf-8").read()


def trecho(fonte: str, inicio: str, fim: str) -> str:
    i = fonte.index(inicio)
    return fonte[i : fonte.index(fim, i + len(inicio))]


# ---------------------------------------------------------------------------
# 1. O alvo e unico
# ---------------------------------------------------------------------------

class TestAlvoUnico(unittest.TestCase):
    """A exigencia central do Fábio: a restricao atinge uma pessoa, uma clinica
    ou uma empresa — e mais ninguem."""

    def test_toda_alavanca_verifica_o_numero_de_atingidos(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for metodo in ["set_user_status", "set_organization_status", "set_membership_status"]:
            with self.subTest(metodo=metodo):
                corpo = trecho(STORE, "def %s" % metodo, "\n    def ")
                assert "_um_alvo_apenas(cursor)" in corpo

    def test_a_verificacao_aborta_acima_de_um(self):
        corpo = trecho(STORE, "def _um_alvo_apenas", "\n    def ")
        assert "cursor.rowcount > 1" in corpo
        assert "raise RuntimeError" in corpo

    def test_a_alteracao_usa_chave_primaria(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for metodo, chave in [
            ("set_user_status", "WHERE id = %s"),
            ("set_organization_status", "WHERE id = %s"),
            ("set_membership_status", "WHERE id = %s"),
        ]:
            with self.subTest(metodo=metodo, chave=chave):
                # Atualizar por e-mail ou por nome abriria espaco para colisao. Todas
                # as tres localizam primeiro e alteram pela chave.
                corpo = trecho(STORE, "def %s" % metodo, "\n    def ")
                assert chave in corpo

    def test_o_vinculo_nao_derruba_as_demais_organizacoes(self):
        corpo = trecho(STORE, "def set_membership_status", "\n    def ")
        assert "membership.organization_id = %s" in corpo

    def test_a_api_exige_a_alavanca_nomeada_na_rota(self):
        # Sem isto, um operador que quisesse tirar acesso a UM cliente poderia
        # desabilitar a pessoa inteira sem perceber.
        for rota in ("/api/admin/access/user", "/api/admin/access/organization",
                     "/api/admin/access/membership"):
            assert '"%s"' % rota in MAIN


# ---------------------------------------------------------------------------
# 2 e 3. A mensagem, e quem nao pode ser bloqueado
# ---------------------------------------------------------------------------

class TestMensagemEFalsosPositivos(unittest.TestCase):
    def test_a_mensagem_e_a_pedida(self):
        assert "Acesso restrito, entre em contato com froid@froid.com.br" in MAIN
        assert "para maiores detalhes" in MAIN

    def test_a_guarda_cobre_login_e_re_hidratacao(self):
        # /api/auth/me e o que o front chama a cada carregamento. Sem a guarda
        # ali, quem foi revogado com a aba aberta so veria telas vazias.
        assert MAIN.count("_guard_acesso_revogado") >= 4

    def test_autonomo_sem_vinculo_nenhum_entra(self):
        corpo = trecho(STORE, "def access_was_revoked", "\n    def ")
        assert "total > 0 and ativos == 0" in corpo

    def test_banco_indisponivel_nao_bloqueia(self):
        corpo = trecho(MAIN, "def _guard_acesso_revogado", "def _issue_session")
        assert "except Exception" in corpo
        assert corpo.index("except Exception") < corpo.index("if revogado")

    def test_contexto_sintetico_nao_conta_como_acesso(self):
        """O defeito que passou pelo teste anterior e apareceu no uso real.

        `_tenant_contexts_for_email` fabrica um `_legacy_tenant_context` quando
        o banco nao devolve contexto nenhum -- que e exatamente o estado de uma
        conta com todos os vinculos revogados. A primeira versao da guarda
        checava so se a lista estava vazia, entao via a organizacao sintetica e
        liberava. A conta revogada entrava, e caia num painel sem permissao
        para nada.

        A guarda tem de olhar se ha contexto REAL, e o sintetico se identifica
        sozinho com `legacy_fallback`.
        """
        corpo = trecho(MAIN, "def _guard_acesso_revogado", "def _issue_session")
        assert "legacy_fallback" in corpo
        assert 'contexto.get("legacy_fallback")' in corpo

    def test_a_guarda_nao_confia_na_lista_estar_cheia(self):
        corpo = trecho(MAIN, "def _guard_acesso_revogado", "def _issue_session")
        # A checagem ingenua -- lista nao vazia libera -- e o que deixou passar.
        ingenua = 'if session_user.get("organizations"):' + chr(10) + "        return"
        assert ingenua not in corpo

    def test_o_fallback_legacy_se_identifica(self):
        corpo = trecho(MAIN, "def _legacy_tenant_context", "def _tenant_contexts_for_email")
        assert '"legacy_fallback": True' in corpo

    def test_administrador_nao_se_tranca_para_fora(self):
        corpo = trecho(MAIN, "def admin_set_user_access", "@app.post")
        assert "email == ator" in corpo


# ---------------------------------------------------------------------------
# 4. Sessao ja aberta
# ---------------------------------------------------------------------------

class TestSessaoAberta(unittest.TestCase):
    def test_a_operacao_derruba_a_sessao_em_memoria(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for rota, expira in [
            ("admin_set_user_access", "_expirar_sessoes_de"),
            ("admin_set_organization_access", "_expirar_sessoes_da_organizacao"),
            ("admin_set_membership_access", "_expirar_sessoes_de"),
        ]:
            with self.subTest(rota=rota, expira=expira):
                corpo = trecho(MAIN, "def %s" % rota, "return resultado")
                assert expira in corpo

    def test_o_dado_ja_estava_protegido_por_requisicao(self):
        # A protecao do dado nao depende da expiracao de sessao: o contexto e
        # reconsultado no Postgres a cada chamada.
        corpo = trecho(MAIN, "def _tenant_context_from_request", "def ")
        assert "_attach_tenant_contexts(user)" in corpo
        assert "TENANT_STORE.enabled" in corpo


# ---------------------------------------------------------------------------
# 5. Reversibilidade
# ---------------------------------------------------------------------------

class TestNadaEApagado(unittest.TestCase):
    def test_a_alavanca_usa_update_e_nunca_delete(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for metodo in ["set_user_status", "set_organization_status", "set_membership_status"]:
            with self.subTest(metodo=metodo):
                corpo = trecho(STORE, "def %s" % metodo, "\n    def ")
                assert "UPDATE" in corpo
                assert "DELETE" not in corpo.upper()

    def test_o_estado_de_volta_existe(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for metodo, estado in [
            ("ESTADOS_USUARIO", "active"),
            ("ESTADOS_ORGANIZACAO", "active"),
            ("ESTADOS_VINCULO", "active"),
        ]:
            with self.subTest(metodo=metodo, estado=estado):
                corpo = trecho(STORE, "%s = (" % metodo, ")")
                assert '"%s"' % estado in corpo

    def test_restaurar_vinculo_limpa_a_data_de_revogacao(self):
        corpo = trecho(STORE, "def set_membership_status", "\n    def ")
        assert "ELSE NULL END" in corpo


# ---------------------------------------------------------------------------
# 6. Autorizacao e trilha
# ---------------------------------------------------------------------------

class TestAutorizacaoETrilha(unittest.TestCase):
    def test_so_administrador_opera(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for rota in ["admin_access_snapshot", "admin_set_user_access",
         "admin_set_organization_access", "admin_set_membership_access"]:
            with self.subTest(rota=rota):
                corpo = trecho(MAIN, "def %s" % rota, "\n@app.")
                assert "_require_admin_user(request)" in corpo

    def test_toda_mutacao_entra_na_trilha(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for rota in ["admin_set_user_access", "admin_set_organization_access",
         "admin_set_membership_access"]:
            with self.subTest(rota=rota):
                corpo = trecho(MAIN, "def %s" % rota, "return resultado")
                assert "_record_admin_audit_event" in corpo

    def test_estado_invalido_e_recusado(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for rota in ["admin_set_user_access", "admin_set_organization_access",
         "admin_set_membership_access"]:
            with self.subTest(rota=rota):
                corpo = trecho(MAIN, "def %s" % rota, "return resultado")
                assert "status_code=400" in corpo

    def test_store_desligado_recusa_em_vez_de_fingir_sucesso(self):
        corpo = trecho(MAIN, "def _exigir_store_ativo", "@app.get")
        assert "status_code=503" in corpo


if __name__ == "__main__":
    unittest.main()
