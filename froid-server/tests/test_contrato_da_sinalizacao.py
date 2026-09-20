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
    """So o hub e as rotas de WebSocket, para nao varrer o main inteiro.

    O recorte passou a comecar em `_recusar_websocket` (19/09/2026), e com isso
    entrou tambem a rota `/ws/fusion`. Antes ele pulava as duas coisas, e o
    efeito nao era teorico: as recusas da fusion nunca foram conferidas por este
    arquivo, e as da sinalizacao deixariam de ser no dia em que saissem de um
    `close(` literal — que foi exatamente o que aconteceu.
    """
    inicio = MAIN.index("class RtcSignalManager")
    fim = MAIN.index("def _decode_audio_bytes")
    hub = MAIN[inicio:fim]
    rotas_inicio = MAIN.index("async def _recusar_websocket")
    rotas_fim = MAIN.index("@app.get", MAIN.index('@app.websocket("/ws/rtc/'))
    return hub + MAIN[rotas_inicio:rotas_fim]


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
        """Todo numero de fechamento que a sinalizacao emite.

        Pega tanto `close(code=4401)` quanto a forma condicional
        `close(code=4402 if ... else 1013)` — foi o 1013 dessa segunda forma
        que passou despercebido.

        E pega tambem `_recusar_websocket(websocket, 4403)`. Em 19/09/2026 as
        recusas passaram a ir por esse helper, porque fechar antes do `accept()`
        fazia o uvicorn descartar o codigo e responder HTTP 403 — o cliente via
        1006 e reconectava oito vezes contra uma recusa deterministica. Sem
        acrescentar a forma nova aqui, esta varredura encontraria apenas
        {4000, 1008} e daria por cumprida uma garantia que teria parado de
        valer: o teste continuaria verde e vazio.
        """
        codigos: set = set()
        chamadas = re.findall(r"close\(([^)]*)\)", TRECHO)
        chamadas += re.findall(r"_recusar_websocket\(([^)]*)\)", TRECHO)
        for chamada in chamadas:
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
        self.assertIn(4404, self.codigos_do_servidor)

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
        # 4401 = o login do profissional nao vale mais; 4404 = a sessao e de
        # outra conta; 4403 = convite invalido ou fora da janela; 4402 = sem
        # credito; 1008 = papel invalido. Um unico "Sinalizacao indisponivel"
        # para todos deixa quem esta na tela sem nenhuma acao possivel — e quem
        # esta na tela e um profissional com um paciente esperando.
        self.assertIn("motivoDaRecusaDeSinalizacao", WEBRTC)
        for codigo in ("4401", "4402", "4403", "4404", "4405", "1008"):
            self.assertIn(codigo, WEBRTC)

    def test_toda_recusa_grava_o_proprio_codigo(self):
        """Recusa registrada sem motivo e recusa pela metade.

        Ate 20/09/2026 as seis causas produziam a mesma linha
        `"outcome":"denied"` no log, sem dizer qual tinha sido. Descobrir exigia
        deduzir pelo unico sinal indireto que sobrava — se o evento trazia
        `organization_id` preenchido, porque so o ramo do recorte por
        organizacao passava `context`. Custou uma investigacao inteira num dia
        com paciente esperando.

        A varredura pareia cada `_recusar_websocket(..., N)` com o
        `close_code=` do audit que o precede, no mesmo bloco.
        """
        recusas = re.findall(
            r'outcome="denied"(.{0,80}?)\n\s*\)\s*\n\s*await (?:_recusar_websocket\(websocket, |websocket\.accept)',
            TRECHO,
            re.DOTALL,
        )
        self.assertTrue(recusas, "a varredura nao encontrou recusa nenhuma")
        sem_codigo = [trecho for trecho in recusas if "close_code=" not in trecho]
        self.assertEqual(
            sem_codigo,
            [],
            f"recusa que nao grava o proprio codigo no log: {sem_codigo}",
        )

    def test_o_login_vencido_nao_acusa_a_conta_errada(self):
        # Ate 20/09/2026 os dois casos saiam pelo mesmo 4401, com a frase do
        # 4404. Num atendimento real o profissional leu "esta sessao pertence a
        # outra conta" e foi conferir a conta, que estava certa, enquanto o que
        # tinha acabado era o login dele. Sao acoes opostas: uma manda trocar de
        # login, a outra manda entrar de novo no mesmo.
        trecho = MAIN[MAIN.index("async def websocket_fusion") :][:2500]
        self.assertIn("if not user:", trecho)
        self.assertIn("_recusar_websocket(websocket, 4401)", trecho)
        self.assertIn("_recusar_websocket(websocket, 4404)", trecho)

    def test_os_dois_lados_usam_a_explicacao(self):
        self.assertIn("motivoDaRecusaDeSinalizacao", PROFISSIONAL)
        self.assertIn("motivoDaRecusaDeSinalizacao", PACIENTE)

    def test_o_recorte_por_organizacao_nao_recusa_o_dono_da_sessao(self):
        """Autoria antes de recorte — decisao do dono do produto, 20/09/2026.

        Nas duas rotas de WebSocket o teste de organizacao roda DEPOIS do teste
        de dono. Quando ele roda, portanto, ja esta provado que quem conecta e o
        autor daquela sessao: ele so conseguiria barrar essa mesma pessoa,
        operando sob outra organizacao da propria conta. Nao protege ninguem de
        ninguem — disso o teste de dono ja cuidou.

        Em 20/09/2026 ele barrou onze vezes, no comeco de um atendimento real,
        sem saida possivel na tela: o painel clinico nao tem seletor de
        organizacao. A divergencia passou a ser anotada no log em vez de virar
        recusa, porque ela ainda e sintoma de uma duplicacao de organizacoes
        aberta no banco.

        Este teste falha se alguem voltar a recusar ali — e a ORDEM tambem e
        afirmada, porque sem ela o argumento inteiro cai.
        """
        for rota in ("async def websocket_fusion", "async def websocket_rtc_signaling"):
            trecho = MAIN[MAIN.index(rota) :]
            trecho = trecho[: trecho.index("\n@app.")] if "\n@app." in trecho else trecho

            dono = trecho.index("SESSION_OWNERS.get(session_id) !=")
            organizacao = trecho.index("if not _session_matches_context(session_id, context):")
            self.assertLess(
                dono,
                organizacao,
                f"{rota}: o teste de dono precisa vir ANTES do de organizacao",
            )

            # Recorte ancorado em sintaxe, e nao em contagem de caracteres: o
            # bloco do profissional termina no `else:` do paciente (rota de
            # sinalizacao) ou na conexao do hub (rota de fusao). Uma janela de
            # N caracteres engoliria o ramo do paciente, que continua recusando
            # por 4403 com toda razao — e o teste acusaria o lugar errado.
            bloco = trecho[organizacao:]
            for fronteira in ("\n    else:", "\n    connection_id = await manager.connect"):
                corte = bloco.find(fronteira)
                if corte != -1:
                    bloco = bloco[:corte]

            self.assertIn('outcome="organization_mismatch"', bloco)
            self.assertNotIn("_recusar_websocket", bloco)
            self.assertNotIn("return", bloco)

    def test_o_canal_de_analise_tambem_le_o_codigo(self):
        """A recusa do `/ws/fusion` nao chegava a lugar nenhum.

        O teste acima conferia que `motivoDaRecusaDeSinalizacao` APARECE em
        LiveSession.tsx — e aparecia, no socket da chamada. O socket de ANALISE,
        que e por onde chegam F0, MFCC, sub-harmonicos e as AUs, ignorava
        `event.code` e reconectava sempre. Em 20/09/2026, num atendimento real,
        ele ficou em laco contra um 4401 a cada cinco segundos SEM UMA LINHA NA
        TELA: audio e video perfeitos, e nenhuma medida sendo apurada.

        O teste passava porque afirmava o mecanismo em algum lugar do arquivo, e
        nao a garantia em cada socket (secao 3 do guia de rigor). O recorte
        abaixo e ancorado em sintaxe, e nao em contagem de caracteres, para nao
        quebrar no proximo comentario que crescer.
        """
        inicio = PROFISSIONAL.index("/ws/fusion/")
        fim = PROFISSIONAL.index("socket.onmessage", inicio)
        trecho = PROFISSIONAL[inicio:fim]
        self.assertIn("deveReconectarAnalise(event.code)", trecho)
        self.assertIn("motivoDaRecusaDeSinalizacao(event.code)", trecho)


if __name__ == "__main__":
    unittest.main()
