"""Fase 7.4, etapa 5: comercio V1 aposentado.

Com o interruptor ligado, checkout, confirmacao, recarga e webhook V1 respondem
410, e a recarga automatica nunca chega ao Stripe. Motivo apurado em producao
em 05/10/2026: uma conta convertida ao V2 ainda tinha cartao salvo com recarga
automatica V1 ligada; uma cobranca V1 ali seria paga sem virar credito.
"""

import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402

ROTAS_V1 = [
    "/api/subscriptions/checkout",
    "/api/subscriptions/confirm-checkout",
    "/api/subscriptions/recharge/retry",
    "/api/stripe/webhook",
]


@pytest.mark.parametrize("rota", ROTAS_V1)
def test_rota_v1_responde_410_com_o_interruptor(monkeypatch, rota):
    monkeypatch.setattr(main, "FROID_V1_COMMERCE_RETIRED", True)
    resposta = TestClient(main.app).post(rota, json={})
    assert resposta.status_code == 410
    assert "Psique V2" in resposta.json()["detail"]


def test_sem_o_interruptor_a_guarda_nao_interfere(monkeypatch):
    monkeypatch.setattr(main, "FROID_V1_COMMERCE_RETIRED", False)
    main._v1_commerce_retired_guard()


def test_recarga_automatica_nunca_chega_ao_stripe(monkeypatch):
    monkeypatch.setattr(main, "FROID_V1_COMMERCE_RETIRED", True)
    chamadas = []

    class Loja:
        def prepare_auto_recharge(self, **kwargs):
            chamadas.append(kwargs)
            return None

    monkeypatch.setattr(main, "TENANT_STORE", Loja())
    asyncio.run(main._run_automatic_recharge("org-qualquer"))
    assert chamadas == []


def test_config_publica_avisa_a_tela(monkeypatch):
    monkeypatch.setattr(main, "FROID_V1_COMMERCE_RETIRED", True)
    assert main.auth_config()["v1_commerce_retired"] is True
