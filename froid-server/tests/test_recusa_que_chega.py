"""Recusa de WebSocket que o cliente nunca recebeu.

APURADO EM 19/09/2026, DEPOIS DE UMA CONSULTA ABANDONADA AOS 2min30.

O profissional abriu a sessao, o paciente abriu o link e liberou camera e
microfone em tres segundos, e a chamada nunca subiu. A tela dele dizia que
faltava o paciente liberar a midia — sobre um paciente que ja tinha liberado — e
nada mais aconteceu. Ele encerrou.

O DEFEITO

As duas rotas de WebSocket recusavam acesso assim:

    await websocket.close(code=4403)     # sem accept() antes

Isso nao entrega codigo nenhum. O uvicorn, ao receber `websocket.close` ANTES do
handshake, descarta o codigo e responde a negociacao HTTP com 403:

    elif message_type == "websocket.close":
        self.logger.info('%s - "WebSocket %s" 403', ...)
        self.initial_response = (http.HTTPStatus.FORBIDDEN, [], b"")

(`uvicorn/protocols/websockets/websockets_impl.py`. O ramo que entrega o codigo
de verdade e o de baixo, `await self.close(code, reason)`, alcancavel so depois
do handshake.)

O navegador entao ve o handshake falhar e entrega ao `onclose` o codigo 1006.
1006 nao esta em `TERMINAL_SIGNALING_CLOSE_CODES`, entao o cliente RECONECTA —
oito vezes, com recuo exponencial, cerca de 23 segundos contra uma recusa
deterministica — e no fim mostra a frase generica. As quatro frases escritas
para dizer o motivo (conta errada, saldo, convite invalido, cadastro pendente)
eram inalcancaveis: existiam, estavam corretas, e nada podia exibi-las.

E quando o recusado e o PACIENTE, o profissional nao ve recusa nenhuma: o
paciente simplesmente nunca entra na sala, nenhum `peer-joined` chega, nenhuma
oferta e feita, e o painel fica em "Aguardando paciente..." indefinidamente.

POR QUE O TESTE ANTIGO NAO PEGOU

`test_contrato_da_sinalizacao.py` confere que todo codigo que o servidor emite
esta na lista de terminais do cliente. Os codigos batiam nos dois lados. O que
ninguem perguntou foi se o codigo CHEGA — a garantia, e nao o mecanismo.
"""
import ast
import asyncio
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MAIN_TEXT = (SERVER_DIR / "main.py").read_text(encoding="utf-8")


class FalsoWebSocket:
    """So registra a ORDEM. E a ordem que decide se o codigo viaja."""

    def __init__(self):
        self.chamadas: list[str] = []

    async def accept(self):
        self.chamadas.append("accept")

    async def close(self, code=1000):
        self.chamadas.append(f"close:{code}")


class RecusaEntregaOMotivoTests(unittest.TestCase):
    def test_o_helper_aceita_antes_de_fechar(self):
        import main

        ws = FalsoWebSocket()
        asyncio.run(main._recusar_websocket(ws, 4403))
        self.assertEqual(
            ws.chamadas,
            ["accept", "close:4403"],
            "fechar antes do accept faz o uvicorn descartar o codigo e responder 403",
        )

    def test_o_codigo_pedido_e_o_codigo_enviado(self):
        import main

        for codigo in (4401, 4402, 4403, 1013):
            with self.subTest(codigo=codigo):
                ws = FalsoWebSocket()
                asyncio.run(main._recusar_websocket(ws, codigo))
                self.assertEqual(ws.chamadas[-1], f"close:{codigo}")

    def test_cliente_que_sumiu_no_meio_nao_derruba_a_rota(self):
        """Recusar quem ja foi embora nao pode virar excecao na rota."""
        import main

        class WebSocketQueMorreu(FalsoWebSocket):
            async def accept(self):
                raise RuntimeError("cliente desistiu do handshake")

        asyncio.run(main._recusar_websocket(WebSocketQueMorreu(), 4401))


class NenhumaRotaFechaAntesDeAceitarTests(unittest.TestCase):
    """A regra varrida no arquivo inteiro, e nao nas sete ocorrencias de hoje.

    Corrigir a ocorrencia e nao a regra ja custou caro aqui. Uma recusa nova,
    escrita a mao daqui a um mes, cai neste teste.
    """

    @staticmethod
    def _rotas_de_websocket() -> list[ast.AsyncFunctionDef]:
        arvore = ast.parse(MAIN_TEXT)
        rotas = []
        for no in ast.walk(arvore):
            if not isinstance(no, ast.AsyncFunctionDef):
                continue
            for dec in no.decorator_list:
                alvo = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(alvo, ast.Attribute) and alvo.attr == "websocket":
                    rotas.append(no)
                    break
        return rotas

    def test_a_varredura_encontra_as_rotas(self):
        nomes = {r.name for r in self._rotas_de_websocket()}
        self.assertIn("websocket_fusion", nomes)
        self.assertIn("websocket_rtc_signaling", nomes)

    # A comparacao por NUMERO DE LINHA nao serve, e a primeira versao deste
    # teste caiu nisso: ela usava o primeiro `accept` da funcao, e na rota de
    # sinalizacao esse `accept` e o do ramo de papel invalido — outro caminho de
    # execucao. As quatro recusas de autorizacao vinham depois dele no arquivo e
    # passavam, embora nenhuma delas jamais o execute. O teste aprovava
    # justamente a rota onde estava o defeito.
    #
    # O que decide e o FLUXO: um `accept` so cobre um `close` se estiver antes
    # dele num bloco que contem os dois. Ramo irmao nao cobre.
    @staticmethod
    def _caminhos(rota):
        """Para cada no, o caminho (bloco, indice) da raiz ate ele."""
        caminhos: dict[int, tuple] = {}

        def visitar(stmts, prefixo):
            for i, st in enumerate(stmts):
                aqui = prefixo + ((id(stmts), i),)
                for n in ast.walk(st):
                    caminhos[id(n)] = aqui
                for campo in ("body", "orelse", "finalbody"):
                    sub = getattr(st, campo, None)
                    if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                        visitar(sub, aqui)
                for handler in getattr(st, "handlers", []) or []:
                    visitar(handler.body, aqui)

        visitar(rota.body, ())
        return caminhos

    @staticmethod
    def _cobre(caminho_accept, caminho_close) -> bool:
        pares = zip(caminho_accept, caminho_close)
        for nivel, ((bloco_a, i_a), (bloco_c, i_c)) in enumerate(pares):
            if bloco_a != bloco_c:
                return False
            if i_a != i_c:
                # Estar num indice anterior do bloco NAO basta. A segunda versao
                # deste teste parou aqui e voltou a aprovar a rota de
                # sinalizacao: o `accept` do ramo de papel invalido e o
                # statement 0 do corpo, e as recusas de autorizacao sao o
                # statement 1 — indice menor, e ainda assim outro caminho, que
                # termina em `return` e nunca alcanca as recusas.
                #
                # Para cobrir, o `accept` tem de ser statement DESTE bloco, e
                # nao algo aninhado dentro de um ramo condicional anterior.
                return i_a < i_c and len(caminho_accept) == nivel + 1
        return False

    def test_todo_close_tem_accept_no_MESMO_caminho(self):
        faltando = []
        for rota in self._rotas_de_websocket():
            caminhos = self._caminhos(rota)

            def chamadas(attr, exigir_websocket):
                for no in ast.walk(rota):
                    if not (
                        isinstance(no, ast.Call)
                        and isinstance(no.func, ast.Attribute)
                        and no.func.attr == attr
                    ):
                        continue
                    if exigir_websocket and not (
                        isinstance(no.func.value, ast.Name)
                        and no.func.value.id == "websocket"
                    ):
                        continue
                    yield no

            aceites = [caminhos[id(n)] for n in chamadas("accept", False)]
            for fechamento in chamadas("close", True):
                caminho = caminhos[id(fechamento)]
                if not any(self._cobre(a, caminho) for a in aceites):
                    faltando.append(f"{rota.name}:{fechamento.lineno}")
        self.assertEqual(
            sorted(faltando),
            [],
            "close() sem accept() no mesmo caminho: o uvicorn descarta o codigo, "
            f"responde HTTP 403 e o cliente ve 1006 — {sorted(faltando)}",
        )


if __name__ == "__main__":
    unittest.main()
