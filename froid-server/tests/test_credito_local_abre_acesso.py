"""Credito que se gasta e acesso que nao abre nao podem conviver.

Apurado em 26/08/2026, com um atendimento marcado e o titular preso na tela de
administracao.

O `access_status` da conta dizia tudo: `selected_plan` preenchido,
`remaining_sessions: 2`, `cpf_required: false`, `manual_approval_ready: true` —
e `onboarding_required: true`. O unico campo fora do lugar era
`payment_status: 'local_applied'`.

`access_ready` comparava contra a lista escrita a mao {"paid","active",
"trialing"}, e ela deixava de fora os DOIS status que o proprio servidor grava
quando aplica credito sem passar pelo Stripe — `local_applied` (pacote com
valor) e `paid_local` (pacote de valor zero). Os dois saem da mesma chamada de
`_apply_session_credit_purchase`.

O resultado nao era uma protecao pela metade por acaso: as sessoes creditadas
por esse caminho SAO consumiveis, e o titular tinha gasto 25 das 27. O portao
recusava o status e liberava o consumo. Uma das duas leituras esta errada, e
nao pode ser a que ja aconteceu 25 vezes.

Quem de fato protege contra credito indevido e
FROID_ALLOW_LOCAL_BILLING_FALLBACK, `false` por padrao, que decide se o caminho
local pode ser usado. Essa e a trava. A lista de status so descreve o passado.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from subscriptions import PAID_SESSION_STATUSES  # noqa: E402

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")


class OsStatusQueSignificamCreditoAplicado(unittest.TestCase):
    def test_inclui_os_dois_status_gravados_pelo_caminho_local(self):
        # Sao os dois valores literais de _apply_session_credit_purchase.
        self.assertIn("local_applied", PAID_SESSION_STATUSES)
        self.assertIn("paid_local", PAID_SESSION_STATUSES)

    def test_continua_incluindo_os_de_sempre(self):
        for status in ("paid", "active", "trialing"):
            self.assertIn(status, PAID_SESSION_STATUSES)

    def test_nao_aceita_status_de_quem_nao_pagou(self):
        for status in ("", "not_started", "pending_checkout", "failed",
                       "subscription_unavailable", "canceled"):
            self.assertNotIn(status, PAID_SESSION_STATUSES)

    def test_todo_status_gravado_pela_compra_esta_coberto(self):
        """A lista tem de acompanhar quem grava, e nao o contrario.

        Le os literais que `_apply_session_credit_purchase` recebe em `status=`
        dentro de main.py. Um caminho de credito novo que grave um status
        inedito reprova aqui, em vez de reproduzir o defeito: creditar sessao e
        deixar a conta parecendo nao paga.
        """
        gravados = set(re.findall(r'status="([a-z_]+)"[^\n]*\n?\s*\)', MAIN))
        # Restringe aos que aparecem junto de aplicacao de credito.
        for trecho in re.finditer(
            r"_apply_session_credit_purchase\((.{0,900}?)\)\n", MAIN, re.S
        ):
            for achado in re.finditer(r'status=(?:")([a-z_]+)(?:")', trecho.group(1)):
                gravados.add(achado.group(1))
            for achado in re.finditer(
                r'status="([a-z_]+)" if .+? else "([a-z_]+)"', trecho.group(1)
            ):
                gravados.add(achado.group(1))
                gravados.add(achado.group(2))
        encontrados = {s for s in ("paid", "paid_local", "local_applied") if s in gravados}
        self.assertTrue(
            encontrados,
            "nao localizei nenhum status de credito em main.py — o teste perdeu o alvo",
        )
        faltando = encontrados - PAID_SESSION_STATUSES
        self.assertEqual(
            faltando, set(),
            f"status que credita sessao e nao abre acesso: {sorted(faltando)}",
        )


class OPortaoNaoVoltaAEscreverAListaAMao(unittest.TestCase):
    def test_access_ready_usa_a_constante(self):
        self.assertIn("payment_status in PAID_SESSION_STATUSES", MAIN)

    def test_a_lista_literal_nao_reaparece(self):
        # Foi a copia escrita a mao que divergiu de quem grava.
        self.assertNotIn('payment_status in {"paid", "active", "trialing"}', MAIN)

    def test_a_trava_de_verdade_continua_no_lugar(self):
        # Aceitar o status nao afrouxa nada: o que impede credito indevido e a
        # variavel que decide se o caminho local pode ser usado, e ela e falsa
        # por padrao.
        self.assertIn('"FROID_ALLOW_LOCAL_BILLING_FALLBACK", "false"', MAIN)
        self.assertIn("if not FROID_ALLOW_LOCAL_BILLING_FALLBACK:", MAIN)


if __name__ == "__main__":
    unittest.main()
