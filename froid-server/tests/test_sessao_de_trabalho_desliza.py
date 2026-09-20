"""A sessao de trabalho do profissional nao pode vencer no meio da consulta.

APURADO EM 20/09/2026, DURANTE UM ATENDIMENTO REAL.

A chamada estava perfeita, o paciente falando, e as medicoes pararam. Depois,
ao encerrar, o painel devolveu "nao autenticado" e recusou-se a arquivar o
relatorio — mantendo a sessao aberta para nao perder a transcricao, que foi a
unica coisa que funcionou como deveria ali.

A CAUSA

`_session_expires_at` era escrito uma vez so, na emissao do token, e nada o
renovava. A sessao de trabalho morria FROID_SESSION_TOKEN_TTL_SECONDS (8h por
padrao) depois do LOGIN, estivesse em uso ou nao. Quem entrou de manha e
atendeu no fim do dia teve o prazo vencendo com um paciente do outro lado.

Foi descartado que fosse reinicio do servidor: `docker inspect` mostrou o
backend de pe desde a vespera, com RestartCount 0. E tambem nao era expiracao
"correta" — era um prazo contado do lugar errado.

O QUE ESTE ARQUIVO AFIRMA

A garantia, e nao o mecanismo: quem esta usando o sistema continua dentro, e
quem parou de usar expira no mesmo tempo de inatividade de antes. Nenhuma
janela foi alargada.

Os testes importam `main` de verdade — o interpretador com dependencias e
`froid-server/.venv-win/Scripts/python.exe`. Sem ele a suite e PULADA, e nao
silenciosamente aprovada.
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

try:
    import main
except Exception as erro:  # pragma: no cover - ambiente sem fastapi
    main = None
    MOTIVO = f"main.py nao importavel neste interpretador: {erro}"


@unittest.skipIf(main is None, "requer o interpretador com as dependencias")
class SessaoDeTrabalhoDeslizaTests(unittest.TestCase):
    def setUp(self):
        self.token = "token-de-teste-da-sessao-deslizante"
        self.addCleanup(main.SESSION_USERS.pop, self.token, None)

    def _gravar(self, faltando_segundos: float) -> dict:
        """Poe na memoria uma sessao que vence daqui a `faltando_segundos`."""
        agora = datetime.now(timezone.utc).timestamp()
        usuario = {
            "email": "profissional@exemplo.com",
            "_session_expires_at": agora + faltando_segundos,
        }
        main.SESSION_USERS[self.token] = usuario
        return usuario

    def test_usar_o_sistema_empurra_o_prazo(self):
        # O caso do incidente: a sessao estava a um minuto de vencer enquanto o
        # profissional atendia. Cada requisicao dele tem de renovar o prazo.
        usuario = self._gravar(faltando_segundos=60)
        antes = usuario["_session_expires_at"]

        resolvido = main._session_user_for_token(self.token)

        self.assertIsNotNone(resolvido)
        self.assertGreater(
            main.SESSION_USERS[self.token]["_session_expires_at"],
            antes,
            "usar o sistema nao renovou o prazo da sessao",
        )

    def test_o_prazo_renovado_e_a_janela_inteira(self):
        # E a janela cheia a partir de agora, e nao um acrescimo arbitrario:
        # escolher outro numero aqui seria escolher um limiar sem dado.
        self._gravar(faltando_segundos=60)
        agora = datetime.now(timezone.utc).timestamp()

        main._session_user_for_token(self.token)

        renovado = main.SESSION_USERS[self.token]["_session_expires_at"]
        self.assertAlmostEqual(
            renovado - agora,
            main.FROID_SESSION_TOKEN_TTL_SECONDS,
            delta=5,
        )

    def test_sessao_parada_alem_da_janela_continua_morrendo(self):
        # O que mudou e de ONDE a janela e contada, nao o tamanho dela. Quem
        # largou a aba aberta e nao usou continua expirando.
        self._gravar(faltando_segundos=-1)

        self.assertIsNone(main._session_user_for_token(self.token))
        self.assertNotIn(
            self.token,
            main.SESSION_USERS,
            "sessao vencida tem de sair da memoria, e nao so ser recusada",
        )

    def test_token_desconhecido_nao_vira_sessao(self):
        # Verificador que aprova qualquer coisa nao verifica nada.
        self.assertIsNone(main._session_user_for_token("token-que-nunca-existiu"))
        self.assertIsNone(main._session_user_for_token(""))

    def test_a_renovacao_vale_para_o_websocket_tambem(self):
        # As rotas de WebSocket resolvem o token por esta mesma funcao — é por
        # ela que passam /ws/fusion e /ws/rtc. Se um dia deixarem de usá-la, a
        # renovação não as alcançaria e o canal de análise voltaria a cair no
        # meio do atendimento sem que nada mais quebrasse.
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        trecho = fonte[fonte.index("async def websocket_fusion") :][:600]
        self.assertIn("_session_user_for_token(token)", trecho)


if __name__ == "__main__":
    unittest.main()
