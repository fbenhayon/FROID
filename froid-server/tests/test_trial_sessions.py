"""Sessoes de cortesia: concessao, bloqueio e o que NAO pode ser alcancado.

O risco deste item nunca foi conceder credito — foi bloquear demais. A garantia
publicada em precos.html e que uma sessao ja realizada nunca e recusada nem
descartada. Metade dos testes aqui existe para provar que o bloqueio novo nao
encosta nesse caminho.
"""

import ast
import sys
import typing
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

FONTE = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
ARVORE = ast.parse(FONTE)


def _funcao(nome: str):
    """Extrai a funcao real do main.py e a executa isolada.

    Importar main aqui exigiria fastapi e cryptography, que nao estao no
    ambiente de teste. Extrair pela AST garante que o testado e o codigo que vai
    rodar — e nao uma reimplementacao que pode divergir em silencio.
    """
    alvo = next(
        n for n in ARVORE.body
        if isinstance(n, ast.FunctionDef) and n.name == nome
    )
    ns = {"Optional": typing.Optional, "_local_int": _local_int}
    exec(ast.get_source_segment(FONTE, alvo), ns)  # noqa: S102
    return ns[nome]


def _local_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


trial_state = _funcao("_trial_state")


def perfil(**campos):
    base = {"trial_sessions": 5, "used_sessions": 0}
    base.update(campos)
    return base


class EstadoDaCortesiaTests(unittest.TestCase):
    def test_cadastro_novo_comeca_com_o_lote_inteiro(self):
        e = trial_state(perfil())
        self.assertTrue(e["on_trial"])
        self.assertEqual(e["trial_remaining"], 5)
        self.assertFalse(e["trial_exhausted"])

    def test_esgota_exatamente_na_quinta(self):
        self.assertFalse(trial_state(perfil(used_sessions=4))["trial_exhausted"])
        self.assertTrue(trial_state(perfil(used_sessions=5))["trial_exhausted"])

    def test_excedente_nao_produz_saldo_negativo(self):
        e = trial_state(perfil(used_sessions=9))
        self.assertEqual(e["trial_remaining"], 0)
        self.assertEqual(e["trial_used"], 5)

    def test_quem_comprou_sai_da_cortesia_para_sempre(self):
        """A distincao que sustenta o item inteiro.

        Cliente que comprou e depois zerou o saldo NAO pode cair no bloqueio:
        para ele vale a regra antiga, de sessao entregue com pendencia de
        acerto. So quem nunca comprou e barrado.
        """
        comprou = perfil(used_sessions=30, session_credit_purchases=[{"id": "p1"}])
        e = trial_state(comprou)
        self.assertFalse(e["on_trial"])
        self.assertFalse(e["trial_exhausted"])

    def test_cadastro_anterior_ao_recurso_nao_ganha_nada(self):
        # Sem trial_sessions no perfil nao ha cortesia: e assim que "so novos
        # cadastros" e garantido, sem varrer a base.
        self.assertFalse(trial_state(perfil(trial_sessions=0))["on_trial"])

    def test_entrada_ausente_ou_corrompida_nao_quebra(self):
        for entrada in (None, {}, "texto", 42, perfil(trial_sessions=-3)):
            e = trial_state(entrada if isinstance(entrada, (dict, type(None))) else None)
            self.assertIn("on_trial", e)
            self.assertGreaterEqual(e["trial_remaining"], 0)

    def test_lista_de_compras_vazia_ainda_e_cortesia(self):
        # [] significa "nenhuma compra", nao "comprou".
        e = trial_state(perfil(used_sessions=5, session_credit_purchases=[]))
        self.assertTrue(e["on_trial"])
        self.assertTrue(e["trial_exhausted"])


class OndeOBloqueioPodeEstarTests(unittest.TestCase):
    """O bloqueio so pode viver nos pontos de INICIO."""

    def _corpo_do_endpoint(self, decorador: str) -> str:
        i = FONTE.index(decorador)
        # Ate o proximo decorador de rota, e nao por N caracteres. O ultimo
        # endpoint do arquivo nao tem sucessor: cair no fim e o caso valido.
        j = FONTE.find("\n@app.", i + len(decorador))
        return FONTE[i:] if j == -1 else FONTE[i:j]

    def test_criar_sessao_bloqueia(self):
        corpo = self._corpo_do_endpoint('@app.post("/session/create")')
        self.assertIn("_trial_blocks_new_session", corpo)

    def test_convite_de_sessao_bloqueia(self):
        corpo = self._corpo_do_endpoint('@app.post("/api/session-invites")')
        self.assertIn("_trial_blocks_new_session", corpo)

    def test_salvar_relatorio_NAO_bloqueia(self):
        """A trava central deste item.

        Se o bloqueio chegar aqui, uma sessao ja atendida passa a ser recusada —
        exatamente o que a pagina de precos promete que nunca acontece.
        """
        corpo = self._corpo_do_endpoint('@app.post("/api/session-reports")')
        self.assertNotIn("_trial_blocks_new_session", corpo)

    def test_resumo_de_sessao_NAO_bloqueia(self):
        # /api/session-summary roda no fim do atendimento. Bloquear aqui
        # derrubaria sessao em andamento.
        corpo = self._corpo_do_endpoint('@app.post("/api/session-summary")')
        self.assertNotIn("_trial_blocks_new_session", corpo)

    def test_o_portao_compartilhado_continua_sem_o_bloqueio(self):
        """_require_professional_feature_access serve dezoito endpoints.

        Colocar o bloqueio dentro dele seria uma linha a menos e um incidente a
        mais: alcancaria o resumo e a leitura de relatorios.
        """
        i = FONTE.index("def _require_professional_feature_access")
        corpo = FONTE[i:FONTE.index("\ndef ", i + 10)]
        self.assertNotIn("_trial_blocks_new_session", corpo)

    def test_websocket_nao_bloqueia(self):
        # O socket exige SESSION_OWNERS ja registrado: a sessao existe antes
        # dele. Bloquear ali recusaria RECONEXAO no meio do atendimento.
        i = FONTE.index('@app.websocket("/ws/fusion/{session_id}")')
        corpo = FONTE[i:FONTE.index("\n@app.", i + 20)]
        self.assertNotIn("_trial_blocks_new_session", corpo)


class ConcessaoTests(unittest.TestCase):
    def test_a_cortesia_e_concedida_so_quando_nao_existe_perfil(self):
        i = FONTE.index("conceder_cortesia = ")
        linha = FONTE[i:FONTE.index("\n", i)]
        self.assertIn("not existing", linha)

    def test_regravar_o_cadastro_nao_renova(self):
        # total_sessions sempre vem do perfil existente; a cortesia so o
        # sobrescreve no ramo de criacao.
        self.assertIn(
            'total_sessions = max(0, _local_int(existing.get("total_sessions")))',
            FONTE,
        )

    def test_a_cortesia_tem_campo_proprio(self):
        # Somar no bonus confundiria cortesia com brinde de compra, e o
        # bloqueio deixaria de saber distinguir quem nunca comprou.
        self.assertIn('"trial_sessions": trial_sessions,', FONTE)
        self.assertIn('"trial_granted_at": trial_granted_at,', FONTE)

    def test_entra_pelo_estado_que_o_portao_ja_aceitava(self):
        # "trialing" ja consta de access_ready e de
        # ACTIVE_SUBSCRIPTION_STATUSES: nenhum portao foi afrouxado.
        self.assertIn('"trialing"', FONTE)
        i = FONTE.index("access_ready = (")
        self.assertIn(
            'payment_status in {"paid", "active", "trialing"}',
            FONTE[i:i + 400],
        )

    def test_o_aviso_traz_o_canal_combinado(self):
        self.assertIn('FROID_TRIAL_CONTACT_EMAIL = "froid@froid.com.br"', FONTE)
        i = FONTE.index("def _trial_block_detail")
        self.assertIn("FROID_TRIAL_CONTACT_EMAIL", FONTE[i:i + 400])


if __name__ == "__main__":
    unittest.main()
