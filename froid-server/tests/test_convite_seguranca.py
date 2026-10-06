"""Seguranca do aceite publico do convite de profissional (revisao de 06/10/2026).

O aceite publico cria a senha no e-mail do convite. Isso so e seguro quando o
e-mail NAO tem identidade no FROID. Antes desta revisao:
- conta so-Google (sem credencial de senha) recebia uma senha criada por quem
  tivesse o link -- o administrador de qualquer clinica tomava a conta inteira;
- credencial nao verificada (cadastro abandonado de outra pessoa) era aceita e
  promovida a verificada;
- aceitar reativava usuario desativado pela plataforma;
- papel de gestao (owner/administrator) ia para quem tivesse o link.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402

EMAIL = "convidado@clinica.test"


class Loja:
    enabled = True

    def __init__(self, *, status="", papeis=("professional",), convite_status="pending"):
        self.status = status
        self.papeis = list(papeis)
        self.convite_status = convite_status
        self.aceites = []

    def member_invitation_details(self, *, token_hash):
        return {"invited_email": EMAIL, "roles": self.papeis, "status": self.convite_status,
                "expired": False, "clinic_name": "Clinica Teste"}

    def user_status(self, email):
        return self.status

    def accept_member_invitation(self, **kwargs):
        self.aceites.append(kwargs)
        return {"organization_id": "org", "membership_id": "m", "user_id": "u"}

    def record_access_audit(self, **kwargs):
        pass


@pytest.fixture
def ambiente(monkeypatch):
    credenciais, perfis = {}, {}
    monkeypatch.setattr(main, "PROFESSIONAL_CREDENTIALS", credenciais)
    monkeypatch.setattr(main, "PROFESSIONAL_PROFILES", perfis)
    monkeypatch.setattr(main, "_save_identity_state", lambda: None)
    monkeypatch.setattr(main, "_issue_session", lambda user: {"token": "t", "user": user})
    main.RATE_LIMIT_BUCKETS.clear()

    def preparar(**kw):
        loja = Loja(**kw)
        monkeypatch.setattr(main, "TENANT_STORE", loja)
        return loja

    return credenciais, perfis, preparar


def _aceitar(corpo):
    return TestClient(main.app).post("/api/organization-invitations/tok123/accept", json=corpo)


def test_conta_so_google_nao_ganha_senha_pelo_link(ambiente):
    credenciais, _perfis, preparar = ambiente
    loja = preparar(status="active")  # identidade existe (Google), sem senha
    r = _aceitar({"name": "Intruso", "password": "abc12345", "password_confirm": "abc12345"})
    assert r.status_code == 409 and "Google" in r.json()["detail"]
    assert EMAIL not in credenciais and loja.aceites == []


def test_perfil_existente_sem_senha_tambem_e_protegido(ambiente):
    credenciais, perfis, preparar = ambiente
    preparar(status="")
    perfis[EMAIL] = {"account_type": "individual"}
    r = _aceitar({"name": "Intruso", "password": "abc12345", "password_confirm": "abc12345"})
    assert r.status_code == 409 and EMAIL not in credenciais


def test_usuario_desativado_nao_e_reativado(ambiente):
    _c, _p, preparar = ambiente
    loja = preparar(status="disabled")
    r = _aceitar({"name": "X", "password": "abc12345", "password_confirm": "abc12345"})
    assert r.status_code == 403 and loja.aceites == []


def test_papel_de_gestao_nao_sai_pelo_link_publico(ambiente):
    _c, _p, preparar = ambiente
    loja = preparar(papeis=("administrator",))
    r = _aceitar({"name": "X", "password": "abc12345", "password_confirm": "abc12345"})
    assert r.status_code == 403 and loja.aceites == []


def test_credencial_nao_verificada_e_substituida_e_nunca_promovida(ambiente):
    credenciais, _p, preparar = ambiente
    preparar(status="")
    credenciais[EMAIL] = {"email": EMAIL, "email_verified": False}
    main._set_professional_password(credenciais[EMAIL], "senhaDoAtacante1")
    hash_do_atacante = credenciais[EMAIL]["password_hash"]
    r = _aceitar({"name": "Convidada", "password": "minhaSenha9", "password_confirm": "minhaSenha9"})
    assert r.status_code == 200
    nova = credenciais[EMAIL]
    assert nova["password_hash"] != hash_do_atacante
    assert main._verify_professional_password(nova, "minhaSenha9")
    assert nova["verified_via"] == "clinic_invitation"


def test_senha_provada_existente_exige_a_senha_e_nao_e_alterada(ambiente):
    credenciais, _p, preparar = ambiente
    preparar(status="active")
    credenciais[EMAIL] = {"email": EMAIL, "email_verified": True, "verified_via": "email",
                          "name": "Dona"}
    main._set_professional_password(credenciais[EMAIL], "senhaCerta1")
    assert _aceitar({"password": "errada123"}).status_code == 401
    r = _aceitar({"password": "senhaCerta1"})
    assert r.status_code == 200
    assert credenciais[EMAIL]["verified_via"] == "email"
    assert main._verify_professional_password(credenciais[EMAIL], "senhaCerta1")


def test_conta_nova_e_criada_pelo_link(ambiente):
    credenciais, _p, preparar = ambiente
    loja = preparar(status="")
    r = _aceitar({"name": "Nova", "password": "abc12345", "password_confirm": "abc12345"})
    assert r.status_code == 200 and len(loja.aceites) == 1
    assert credenciais[EMAIL]["email_verified"] is True


def test_link_velho_nao_revela_email_nem_clinica(ambiente):
    _c, _p, preparar = ambiente
    preparar(convite_status="accepted")
    r = TestClient(main.app).get("/api/organization-invitations/tok123")
    assert r.status_code == 200
    assert set(r.json()) == {"status", "expired"}


def test_get_diz_a_tela_qual_caminho_mostrar(ambiente):
    _c, _p, preparar = ambiente
    preparar(status="active")
    corpo = TestClient(main.app).get("/api/organization-invitations/tok123").json()
    assert corpo["google_only"] is True and corpo["has_password"] is False
    preparar(status="", papeis=("owner",))
    assert TestClient(main.app).get("/api/organization-invitations/tok123").json()["requires_session"] is True


def test_identidade_so_do_convite_nao_ganha_trial_gratis(monkeypatch):
    monkeypatch.setattr(main, "PROFESSIONAL_CREDENTIALS", {
        EMAIL: {"email_verified": True, "verified_via": "clinic_invitation"},
        "caixa@x.test": {"email_verified": True, "verified_via": "email"},
    })
    convite = main._psique_v2_identidade_para_trial({"provider": "password"}, EMAIL)
    caixa = main._psique_v2_identidade_para_trial({"provider": "password"}, "caixa@x.test")
    assert convite.legacy_benefit_ref  # trial INELIGIBLE
    assert caixa.legacy_benefit_ref is None
