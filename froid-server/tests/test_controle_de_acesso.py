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

import pytest

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

class TestAlvoUnico:
    """A exigencia central do Fábio: a restricao atinge uma pessoa, uma clinica
    ou uma empresa — e mais ninguem."""

    @pytest.mark.parametrize(
        "metodo",
        ["set_user_status", "set_organization_status", "set_membership_status"],
    )
    def test_toda_alavanca_verifica_o_numero_de_atingidos(self, metodo):
        corpo = trecho(STORE, "def %s" % metodo, "\n    def ")
        assert "_um_alvo_apenas(cursor)" in corpo

    def test_a_verificacao_aborta_acima_de_um(self):
        corpo = trecho(STORE, "def _um_alvo_apenas", "\n    def ")
        assert "cursor.rowcount > 1" in corpo
        assert "raise RuntimeError" in corpo

    @pytest.mark.parametrize(
        "metodo,chave",
        [
            ("set_user_status", "WHERE id = %s"),
            ("set_organization_status", "WHERE id = %s"),
            ("set_membership_status", "WHERE id = %s"),
        ],
    )
    def test_a_alteracao_usa_chave_primaria(self, metodo, chave):
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

class TestMensagemEFalsosPositivos:
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

    def test_administrador_nao_se_tranca_para_fora(self):
        corpo = trecho(MAIN, "def admin_set_user_access", "@app.post")
        assert "email == ator" in corpo


# ---------------------------------------------------------------------------
# 4. Sessao ja aberta
# ---------------------------------------------------------------------------

class TestSessaoAberta:
    @pytest.mark.parametrize(
        "rota,expira",
        [
            ("admin_set_user_access", "_expirar_sessoes_de"),
            ("admin_set_organization_access", "_expirar_sessoes_da_organizacao"),
            ("admin_set_membership_access", "_expirar_sessoes_de"),
        ],
    )
    def test_a_operacao_derruba_a_sessao_em_memoria(self, rota, expira):
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

class TestNadaEApagado:
    @pytest.mark.parametrize(
        "metodo", ["set_user_status", "set_organization_status", "set_membership_status"]
    )
    def test_a_alavanca_usa_update_e_nunca_delete(self, metodo):
        corpo = trecho(STORE, "def %s" % metodo, "\n    def ")
        assert "UPDATE" in corpo
        assert "DELETE" not in corpo.upper()

    @pytest.mark.parametrize(
        "metodo,estado",
        [
            ("ESTADOS_USUARIO", "active"),
            ("ESTADOS_ORGANIZACAO", "active"),
            ("ESTADOS_VINCULO", "active"),
        ],
    )
    def test_o_estado_de_volta_existe(self, metodo, estado):
        corpo = trecho(STORE, "%s = (" % metodo, ")")
        assert '"%s"' % estado in corpo

    def test_restaurar_vinculo_limpa_a_data_de_revogacao(self):
        corpo = trecho(STORE, "def set_membership_status", "\n    def ")
        assert "ELSE NULL END" in corpo


# ---------------------------------------------------------------------------
# 6. Autorizacao e trilha
# ---------------------------------------------------------------------------

class TestAutorizacaoETrilha:
    @pytest.mark.parametrize(
        "rota",
        ["admin_access_snapshot", "admin_set_user_access",
         "admin_set_organization_access", "admin_set_membership_access"],
    )
    def test_so_administrador_opera(self, rota):
        corpo = trecho(MAIN, "def %s" % rota, "\n@app.")
        assert "_require_admin_user(request)" in corpo

    @pytest.mark.parametrize(
        "rota",
        ["admin_set_user_access", "admin_set_organization_access",
         "admin_set_membership_access"],
    )
    def test_toda_mutacao_entra_na_trilha(self, rota):
        corpo = trecho(MAIN, "def %s" % rota, "return resultado")
        assert "_record_admin_audit_event" in corpo

    @pytest.mark.parametrize(
        "rota",
        ["admin_set_user_access", "admin_set_organization_access",
         "admin_set_membership_access"],
    )
    def test_estado_invalido_e_recusado(self, rota):
        corpo = trecho(MAIN, "def %s" % rota, "return resultado")
        assert "status_code=400" in corpo

    def test_store_desligado_recusa_em_vez_de_fingir_sucesso(self):
        corpo = trecho(MAIN, "def _exigir_store_ativo", "@app.get")
        assert "status_code=503" in corpo
