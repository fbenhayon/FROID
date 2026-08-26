""""Configurado" nao e resposta. A pergunta e se o relay ATENDE.

NASCEU DA PERGUNTA CERTA, FEITA PELO DONO DO PRODUTO.

Depois de uma consulta perdida por falta de conexao, eu escrevi tres vezes que
faltava rodar `docker compose ps` para saber se o relay estava no ar. A
resposta veio como critica, e estava certa: existe uma POSTURA no codigo que
aceita "esta configurado" como se fosse "esta funcionando", e enquanto ela
existir a mesma falha volta.

O caso concreto: `/health` publicava

    "turn_configured": bool(FROID_TURN_URLS and FROID_TURN_SECRET)

Numa consulta real isso era `true` — as variaveis estavam preenchidas e
corretas — e o contêiner do relay nunca havia subido, porque o servico
`froid-turn` tem `profiles: ["webrtc"]` no compose e nao entra em
`docker compose up` comum. A checagem dizia "configurado", a chamada nao
conectava, e nada no sistema ligava as duas coisas.

`turn_reachable()` faz a outra pergunta: manda um STUN Binding Request cru e
espera a resposta. Se ninguem atende, ninguem atende — e agora `/health` diz
isso em uma linha, sem precisar de acesso ao servidor.

POR QUE O BINDING SEM AUTENTICACAO BASTA

O coturn responde a Binding Request mesmo com `use-auth-secret` ligado:
autenticacao e exigida para ALOCAR relay, nao para o binding. Entao a sonda
prova que o processo esta vivo e alcancavel naquela porta, que e exatamente o
que faltava saber. Ela nao prova que a alocacao de relay funciona — para isso
seria preciso credencial e uma alocacao de verdade, e uma sonda que aloca relay
a cada /health seria pior que o problema.
"""

import ast
import socket
import threading
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")


def _funcoes_da_sonda():
    """Extrai as funcoes puras do main.py sem importar o modulo.

    main.py importa fastapi, que nao esta instalado no ambiente de teste. Em
    vez de espelhar a logica aqui — copia que envelhece e passa a mentir —
    executamos o codigo REAL das duas funcoes num namespace proprio.
    """
    arvore = ast.parse(MAIN)
    desejadas = {"_turn_endpoints", "_probe_turn_once"}
    corpo = [
        no
        for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name in desejadas
    ]
    assert len(corpo) == len(desejadas), (
        f"nao encontrei {desejadas - {n.name for n in corpo}} em main.py"
    )
    espaco: dict = {"socket": socket, "secrets": __import__("secrets")}
    modulo = ast.Module(body=corpo, type_ignores=[])
    exec(compile(modulo, "<sonda>", "exec"), espaco)
    return espaco


class ServidorStunDeMentira:
    """Responde Binding Request como o coturn responderia."""

    def __init__(self, responder: bool = True):
        self.responder = responder
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.porta = self.sock.getsockname()[1]
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._servir, daemon=True)

    def _servir(self):
        self.sock.settimeout(0.2)
        while not self._parar.is_set():
            try:
                dados, origem = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                return
            if not self.responder or len(dados) < 20:
                continue
            # 0101 = Binding Success, comprimento 0, mesmo cookie e transacao.
            resposta = (
                bytes.fromhex("01010000") + dados[4:8] + dados[8:20]
            )
            try:
                self.sock.sendto(resposta, origem)
            except OSError:
                return

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._parar.set()
        try:
            self.sock.close()
        except OSError:
            pass


class AUrlDoTurnEInterpretada(unittest.TestCase):
    def setUp(self):
        self.espaco = _funcoes_da_sonda()

    def _extrair(self, urls):
        self.espaco["FROID_TURN_URLS"] = urls
        return self.espaco["_turn_endpoints"]()

    def test_forma_usada_em_producao(self):
        self.assertEqual(
            self._extrair(["turn:204.168.229.32:3478?transport=udp"]),
            [("204.168.229.32", 3478)],
        )

    def test_varias_urls_viram_varios_destinos(self):
        self.assertEqual(
            self._extrair(
                [
                    "turn:10.0.0.1:3478?transport=udp",
                    "turn:10.0.0.1:3478?transport=tcp",
                ]
            ),
            [("10.0.0.1", 3478), ("10.0.0.1", 3478)],
        )

    def test_sem_porta_vale_a_padrao_da_rfc(self):
        self.assertEqual(self._extrair(["turn:relay.exemplo"]), [("relay.exemplo", 3478)])

    def test_turns_com_tls_tambem_e_interpretado(self):
        self.assertEqual(
            self._extrair(["turns:relay.exemplo:5349"]), [("relay.exemplo", 5349)]
        )

    def test_url_quebrada_nao_derruba_a_extracao(self):
        # Uma URL ruim nao pode apagar as boas: a sonda precisa continuar
        # respondendo pelos destinos que consegue interpretar.
        self.assertEqual(
            self._extrair(["turn:relay.exemplo:porta-errada", "turn:10.0.0.2:3478"]),
            [("10.0.0.2", 3478)],
        )


class ASondaDistingueQuemAtende(unittest.TestCase):
    """O teste que da sentido ao resto: sonda que sempre diz sim nao serve."""

    def setUp(self):
        self.espaco = _funcoes_da_sonda()

    def test_servidor_que_responde_e_reconhecido(self):
        with ServidorStunDeMentira(responder=True) as servidor:
            self.assertTrue(
                self.espaco["_probe_turn_once"]("127.0.0.1", servidor.porta, 2.0)
            )

    def test_porta_muda_nao_e_reconhecida(self):
        # O caso real: variaveis certas, ninguem atendendo.
        with ServidorStunDeMentira(responder=False) as servidor:
            self.assertFalse(
                self.espaco["_probe_turn_once"]("127.0.0.1", servidor.porta, 0.6)
            )

    def test_porta_fechada_nao_e_reconhecida(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        porta = sock.getsockname()[1]
        sock.close()
        self.assertFalse(self.espaco["_probe_turn_once"]("127.0.0.1", porta, 0.6))

    def test_host_inexistente_nao_derruba_a_sonda(self):
        self.assertFalse(
            self.espaco["_probe_turn_once"]("nao-existe.invalido", 3478, 0.6)
        )


class AResistenciaDaChecagem(unittest.TestCase):
    """O que /health promete continuar fazendo mesmo quando a sonda falha."""

    def test_o_health_publica_alcance_alem_de_configuracao(self):
        self.assertIn('"turn_reachable"', MAIN)
        self.assertIn('"turn_detail"', MAIN)

    def test_o_ready_exige_relay_que_responde_quando_o_relay_e_obrigatorio(self):
        self.assertIn('"rtc_relay_reachable"', MAIN)

    def test_a_sonda_nunca_derruba_o_health(self):
        # Health que quebra quando a checagem quebra e pior que health
        # incompleto: quem o consulta perde ate a informacao que estava boa.
        i = MAIN.index("def _midia_turn(")
        trecho = MAIN[i : i + 700]
        self.assertIn("except Exception", trecho)
        self.assertIn("return False", trecho)

    def test_a_sonda_tem_cache_para_nao_medir_a_cada_chamada(self):
        self.assertIn("_TURN_PROBE_CACHE", MAIN)
        self.assertIn("FROID_TURN_PROBE_TTL_SECONDS", MAIN)

    def test_o_detalhe_ensina_onde_olhar(self):
        # Mensagem de erro que nao diz onde olhar manda a pessoa procurar no
        # lugar errado — foi o que aconteceu com o 403 do NR-1.
        self.assertIn("profiles:[webrtc]", MAIN)
        self.assertIn("49160-49200/udp", MAIN)


class AChaveDoPseudonimoTemForca(unittest.TestCase):
    """A regua da chave juridica passa a valer para a do trabalhador."""

    def test_exige_o_mesmo_minimo_da_chave_juridica(self):
        self.assertIn("FROID_DATAMART_PSEUDONYM_KEY_FORTE", MAIN)
        i = MAIN.index("FROID_DATAMART_PSEUDONYM_KEY_FORTE")
        self.assertIn(">= 32", MAIN[i : i + 200])

    def test_a_checagem_de_prontidao_usa_a_forca_e_nao_a_presenca(self):
        i = MAIN.index('"datamart_pseudonym_key_configured"')
        trecho = MAIN[i : i + 160]
        self.assertIn("FROID_DATAMART_PSEUDONYM_KEY_FORTE", trecho)
        self.assertNotIn("bool(FROID_DATAMART_PSEUDONYM_KEY)", trecho)


if __name__ == "__main__":
    unittest.main()
