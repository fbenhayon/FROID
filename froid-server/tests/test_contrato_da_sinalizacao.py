"""Toda mensagem que atravessa a fronteira precisa de alguem do outro lado.

NASCEU DE UMA CONSULTA PERDIDA, EM 26/08/2026.

Um profissional e seu paciente ficaram trinta minutos sem conseguir estabelecer
video. A tela dele dizia "Reconectando midia do paciente..."; a dela, "Aguardando
chamada do profissional...". Os dois esperando o outro. O atendimento foi
encerrado sem acontecer.

Nada havia regredido. `LiveSession.tsx` nao era tocado desde 11/08, `webrtc.ts`
desde 03/08. Os dois defeitos que produziram o impasse eram ANTIGOS:

  - a guarda `signalingState !== "stable"` em makeOffer e de 16/06/2026
  - o servidor emite `peer-waiting` desde 22/07/2026, e nenhum cliente jamais
    o leu — `grep peer-waiting` no painel inteiro devolvia zero

Por isso "sempre funcionou": os dois so se manifestam DEPOIS de uma queda. Toda
sessao que correu limpa nunca tocou esse caminho. A primeira desconexao
transitoria — e ela sempre chega — virava impasse permanente, sem nada na tela
que dissesse por que.

O QUE ESTE ARQUIVO VERIFICA, E POR QUE ASSIM

O erro de metodo que permitiu isso: procurava-se quem EMITE. Grepar o emissor
encontra `peer-waiting` no servidor e da a impressao de que a funcionalidade
existe. A pergunta que encontra o defeito e a inversa, e e esta:

    para cada mensagem que atravessa a fronteira, QUEM A LE — e o que acontece
    se ninguem ler?

Mensagem sem leitor nao da erro, nao aparece em log, nao quebra teste e nao
falha build. Ela simplesmente nao acontece, e o sintoma nasce a tres camadas de
distancia, num consultorio.

O mesmo vale para codigo de fechamento de WebSocket: fechar com um codigo que o
cliente nao conhece faz o cliente reconectar contra um servidor que vai recusar
para sempre.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

REPO = SERVER_DIR.parent
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
PROFISSIONAL = (
    REPO / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"
).read_text(encoding="utf-8")
PACIENTE = (
    REPO / "froid-dashboard" / "src" / "pages" / "PatientSessionPage.tsx"
).read_text(encoding="utf-8")
WEBRTC = (
    REPO / "froid-dashboard" / "src" / "lib" / "webrtc.ts"
).read_text(encoding="utf-8")


def _trecho_da_sinalizacao() -> str:
    """So o hub e a rota de sinalizacao, para nao varrer o main inteiro."""
    inicio = MAIN.index("class RtcSignalManager")
    fim = MAIN.index("def _decode_audio_bytes")
    hub = MAIN[inicio:fim]
    rota_inicio = MAIN.index('@app.websocket("/ws/rtc/{session_id}/{role}")')
    rota_fim = MAIN.index("@app.get", rota_inicio)
    return hub + MAIN[rota_inicio:rota_fim]


TRECHO = _trecho_da_sinalizacao()

# Tres ou quatro digitos isolados. Compilada uma vez, no topo, porque
# escrever a mesma regex dentro do metodo ja produziu byte de backspace
# no lugar da ancora \b — defeito invisivel que zerou a varredura.
NUMERO_DE_CODIGO = re.compile(r"(?<![0-9])[0-9]{3,4}(?![0-9])")

# O que o servidor EMITE por conta propria. Mensagens apenas repassadas
# (offer/answer/ice/...) nao entram: quem as origina e o outro cliente.
EMITIDAS = set(re.findall(r'"type":\s*"([a-z-]+)"', TRECHO))

LIDAS_PELO_PROFISSIONAL = set(
    re.findall(r'data\.type === "([a-z-]+)"', PROFISSIONAL)
)
LIDAS_PELO_PACIENTE = set(re.findall(r'data\.type === "([a-z-]+)"', PACIENTE))


class TodaMensagemTemLeitor(unittest.TestCase):
    """A trava que teria pego `peer-waiting` em 22/07, e nao em 26/08."""

    def test_a_varredura_encontra_as_mensagens_do_servidor(self):
        """Verificador que nao acha nada nunca e verificador que funciona."""
        self.assertIn("peer-waiting", EMITIDAS)
        self.assertIn("peer-joined", EMITIDAS)
        self.assertIn("signal-ready", EMITIDAS)
        self.assertGreaterEqual(len(EMITIDAS), 4)

    def test_nenhuma_mensagem_do_servidor_fica_sem_leitor(self):
        orfas = sorted(
            EMITIDAS - LIDAS_PELO_PROFISSIONAL - LIDAS_PELO_PACIENTE
        )
        self.assertEqual(
            orfas,
            [],
            "o servidor emite mensagem que NENHUM cliente le: "
            f"{orfas}. Mensagem sem leitor nao da erro, nao aparece em log e "
            "nao quebra build — ela so nao acontece, e o sintoma nasce num "
            "consultorio. Ou trate no cliente, ou pare de emitir.",
        )

    def test_o_profissional_sabe_quando_a_sala_esta_vazia(self):
        # O defeito exato da consulta perdida.
        self.assertIn("peer-waiting", LIDAS_PELO_PROFISSIONAL)

    def test_o_paciente_sabe_quando_o_profissional_chega(self):
        # Sem isto o paciente e passivo: abre o socket, escreve "Aguardando
        # chamada do profissional..." e espera, sem poder pedir nada. Quando o
        # outro lado esta travado, nao ha quem destrave.
        self.assertIn("signal-ready", LIDAS_PELO_PACIENTE)
        self.assertIn("peer-joined", LIDAS_PELO_PACIENTE)


class TodoFechamentoTemTratamento(unittest.TestCase):
    """Fechar com codigo que o cliente nao conhece vira laco de reconexao."""

    @property
    def codigos_do_servidor(self) -> set:
        """Todo numero que aparece dentro de um close(...) da sinalizacao.

        Pega tanto `close(code=4401)` quanto a forma condicional
        `close(code=4402 if ... else 1013)` — foi o 1013 dessa segunda forma
        que passou despercebido.
        """
        codigos: set = set()
        for chamada in re.findall(r"close\(([^)]*)\)", TRECHO):
            codigos.update(int(n) for n in re.findall(NUMERO_DE_CODIGO, chamada))
        return codigos

    @property
    def codigos_terminais_do_cliente(self) -> set:
        achado = re.search(
            r"TERMINAL_SIGNALING_CLOSE_CODES = new Set\(\[([\d,\s]+)\]\)", WEBRTC
        )
        assert achado, "nao encontrei a lista de codigos terminais no cliente"
        return {int(c) for c in re.findall(r"\d+", achado.group(1))}

    def test_a_varredura_encontra_os_codigos(self):
        self.assertIn(4401, self.codigos_do_servidor)
        self.assertIn(4403, self.codigos_do_servidor)

    def test_todo_codigo_de_recusa_e_terminal_no_cliente(self):
        """Recusa nao se resolve tentando de novo.

        Codigo de recusa fora da lista faz o cliente reconectar contra um
        servidor que vai negar sempre — e a tela diz "Reconectando..." enquanto
        isso, que e a mensagem errada para uma porta fechada.
        """
        recusas = {c for c in self.codigos_do_servidor if c >= 4000 or c == 1008}
        faltando = sorted(recusas - self.codigos_terminais_do_cliente)
        self.assertEqual(
            faltando,
            [],
            f"codigo de recusa que o cliente nao reconhece: {faltando}",
        )

    def test_o_codigo_1013_esta_coberto(self):
        # Emitido quando o acesso do profissional falha por motivo
        # nao-financeiro. Estava fora da lista: o cliente reconectava oito
        # vezes contra uma recusa determinista.
        self.assertIn(1013, self.codigos_terminais_do_cliente)


class ARecusaDizQualFoi(unittest.TestCase):
    """Quatro causas diferentes nao podem produzir a mesma frase."""

    def test_o_cliente_distingue_os_motivos_de_recusa(self):
        # 4401 = a sessao nao e desta conta; 4403 = convite invalido ou fora da
        # janela; 4402 = sem credito; 1008 = papel invalido. Um unico
        # "Sinalizacao indisponivel" para os quatro deixa quem esta na tela sem
        # nenhuma acao possivel — e quem esta na tela e um profissional com um
        # paciente esperando.
        self.assertIn("motivoDaRecusaDeSinalizacao", WEBRTC)
        for codigo in ("4401", "4402", "4403", "1008"):
            self.assertIn(codigo, WEBRTC)

    def test_os_dois_lados_usam_a_explicacao(self):
        self.assertIn("motivoDaRecusaDeSinalizacao", PROFISSIONAL)
        self.assertIn("motivoDaRecusaDeSinalizacao", PACIENTE)


if __name__ == "__main__":
    unittest.main()
