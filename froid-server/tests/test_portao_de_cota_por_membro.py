# -*- coding: utf-8 -*-
"""O portao de cota por membro no inicio da sessao (main._member_quota_block_detail).

Regra do dono (18/10/2026): a sessao so e recusada pelo limite que o
responsavel atribuiu ou pelo esgotamento do pool. A cobranca V2 acontece ao
arquivar e nunca recusa (politica A); o unico lugar em que o limite BARRA e o
inicio da sessao. Aqui o tenant store e um duble; a leitura real da cota
esta em test_psique_member_quota_v2 (PostgreSQL).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

import main  # noqa: E402
from tenant_access import AccessContext  # noqa: E402


def _contexto():
    return AccessContext.create(organization_id="org-1", membership_id="m-1", user_id="u-1",
                                roles=["professional"], organization_type="clinic")


class _Store:
    def __init__(self, cota, erro=None):
        self.enabled = True
        self._cota = cota
        self._erro = erro
        self.chamadas = []

    def member_quota(self, *, organization_id, membership_id):
        self.chamadas.append((organization_id, membership_id))
        if self._erro:
            raise self._erro
        return self._cota


class OPortaoDeCota(unittest.TestCase):
    def test_sem_cota_atribuida_nao_barra(self):
        with patch.object(main, "TENANT_STORE", _Store(None)):
            self.assertEqual(main._member_quota_block_detail(_contexto()), "")

    def test_cota_com_saldo_nao_barra(self):
        store = _Store({"quota_sessions": 3, "consumed_sessions": 2, "remaining": 1})
        with patch.object(main, "TENANT_STORE", store):
            self.assertEqual(main._member_quota_block_detail(_contexto()), "")
        self.assertEqual(store.chamadas, [("org-1", "m-1")])

    def test_cota_esgotada_barra_com_a_frase_escrita_para_o_profissional(self):
        store = _Store({"quota_sessions": 2, "consumed_sessions": 2, "remaining": 0})
        with patch.object(main, "TENANT_STORE", store):
            with self.assertLogs("froid.persistence", level="INFO") as log:
                detalhe = main._member_quota_block_detail(_contexto())
        self.assertEqual(detalhe, main.MEMBER_QUOTA_BLOCK_DETAIL)
        self.assertIn("responsável pela clínica", detalhe)
        self.assertTrue(any("atingiu 2/2 sessoes" in linha for linha in log.output))

    def test_falha_de_leitura_libera_e_fica_no_log(self):
        with patch.object(main, "TENANT_STORE", _Store(None, erro=RuntimeError("banco fora"))):
            with self.assertLogs("froid.persistence", level="ERROR"):
                self.assertEqual(main._member_quota_block_detail(_contexto()), "")

    def test_sem_contexto_ou_sem_tenant_store_nao_barra(self):
        self.assertEqual(main._member_quota_block_detail(None), "")
        with patch.object(main, "TENANT_STORE", SimpleNamespace(enabled=False)):
            self.assertEqual(main._member_quota_block_detail(_contexto()), "")

    def test_a_rota_de_criacao_chama_o_portao_depois_do_portao_v2(self):
        fonte = (SERVIDOR / "main.py").read_text(encoding="utf-8")
        inicio = fonte.index("bloqueio_v2 = _psique_v2_start_block_detail(context) if org_v2 else \"\"")
        trecho = fonte[inicio: inicio + 900]
        self.assertIn("bloqueio_de_cota = _member_quota_block_detail(context)", trecho)
        self.assertIn("raise HTTPException(status_code=402, detail=bloqueio_de_cota)", trecho)
        self.assertLess(trecho.index("bloqueio_de_cota ="), trecho.index("session_id = str(uuid.uuid4())"))


if __name__ == "__main__":
    unittest.main()
