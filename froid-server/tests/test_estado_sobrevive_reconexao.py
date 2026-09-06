"""A medida da sessao sobrevive a reconexao do socket do profissional.

Apurado em 06/09/2026, numa sessao remota de 18 minutos em que o profissional
via e ouvia o paciente e NENHUM indice do servidor funcionava.

`ConnectionManager.connect` construia um `SessionState` NOVO a cada conexao, e
`disconnect` apagava a entrada inteira. O estado, porem, e onde se acumula tudo
o que o dispositivo do PACIENTE alimenta por endpoints proprios — a F0 medida
do PCM, os biomarcadores vocais, as AUs faciais, o buffer rolante de audio — e,
sobretudo, a BASELINE, que exige 60 segundos continuos para travar.

O painel do profissional reconecta com facilidade: ha um watchdog de 8 segundos
que fecha o socket quando o tique nao chega, mais qualquer oscilacao de rede ou
aba em segundo plano. Cada reconexao zerava tudo. Reconectando mais de uma vez
por minuto — e reconectava —, a baseline NUNCA travava, e a sessao inteira
corria publicando "sem apuracao" com o paciente falando normalmente.

O socket e da conexao. A medida e da sessao.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402


class _SocketFalso:
    """Basta responder ao `accept`; nada aqui exercita transporte."""

    def __init__(self) -> None:
        self.aceito = False

    async def accept(self) -> None:
        self.aceito = True


def _gerente() -> "main.ConnectionManager":
    return main.ConnectionManager()


def test_reconexao_preserva_o_estado_da_sessao():
    gerente = _gerente()
    sessao = "froid-teste-reconexao"

    primeira = asyncio.run(gerente.connect(_SocketFalso(), sessao))
    estado = gerente.active_sessions[sessao]["state"]
    # Marca o estado como o PCM do paciente marcaria.
    estado.latest_f0_mean = 187.5

    gerente.disconnect(sessao, primeira)
    asyncio.run(gerente.connect(_SocketFalso(), sessao))

    assert gerente.active_sessions[sessao]["state"] is estado
    assert gerente.active_sessions[sessao]["state"].latest_f0_mean == 187.5


def test_o_pcm_que_chega_durante_a_reconexao_nao_e_descartado():
    """Era o buraco pratico: o paciente envia ~1 janela/s o tempo todo.

    Enquanto o painel reconectava, os endpoints buscavam em `active_sessions`,
    nao achavam nada e devolviam `session_inactive` — o audio subia e o
    servidor jogava fora.
    """
    gerente = _gerente()
    sessao = "froid-teste-janela"

    conexao = asyncio.run(gerente.connect(_SocketFalso(), sessao))
    gerente.disconnect(sessao, conexao)

    assert sessao not in gerente.active_sessions
    assert gerente.state_for(sessao) is not None


def test_sem_sessao_aberta_o_estado_nao_nasce_sozinho():
    """O portao que ja existia continua valendo.

    O dispositivo do paciente nao cria estado por conta propria: se o
    profissional nunca abriu a sessao, a resposta continua sendo recusa.
    """
    gerente = _gerente()
    assert gerente.state_for("sessao-que-ninguem-abriu") is None


def test_encerrar_libera_o_estado():
    gerente = _gerente()
    sessao = "froid-teste-encerra"
    conexao = asyncio.run(gerente.connect(_SocketFalso(), sessao))
    gerente.disconnect(sessao, conexao)
    assert gerente.state_for(sessao) is not None

    gerente.encerrar_sessao(sessao)
    assert gerente.state_for(sessao) is None


def test_estado_vencido_e_descartado():
    """Preservar nao pode virar vazamento.

    Sessao de atendimento tem teto de 55 minutos na interface; o TTL de seis
    horas da folga para pausa, reabertura e relatorio. Sem descarte, cada
    sessao ja encerrada guardaria buffers de audio para sempre.
    """
    gerente = _gerente()
    antiga = "froid-sessao-antiga"
    conexao = asyncio.run(gerente.connect(_SocketFalso(), antiga))
    gerente.disconnect(antiga, conexao)

    registro = gerente.session_states[antiga]
    registro["tocado_em"] = registro["tocado_em"] - gerente.TTL_DO_ESTADO_S - 1

    # Abrir outra sessao dispara a varredura.
    nova = "froid-sessao-nova"
    asyncio.run(gerente.connect(_SocketFalso(), nova))

    assert antiga not in gerente.session_states
    assert nova in gerente.session_states


def test_sessao_viva_nunca_e_descartada_pelo_ttl():
    """Uma sessao COM socket aberto nao pode ser varrida por idade.

    Sem esta guarda, um atendimento longo perderia o estado no meio.
    """
    gerente = _gerente()
    viva = "froid-sessao-viva"
    asyncio.run(gerente.connect(_SocketFalso(), viva))
    registro = gerente.session_states[viva]
    registro["tocado_em"] = registro["tocado_em"] - gerente.TTL_DO_ESTADO_S - 1

    asyncio.run(gerente.connect(_SocketFalso(), "outra-qualquer"))

    assert viva in gerente.session_states


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
