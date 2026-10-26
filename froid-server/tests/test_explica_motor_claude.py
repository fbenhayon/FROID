# -*- coding: utf-8 -*-
"""O caminho Claude do FROID Explica: primeiro na fila, honesto quando cai.

Fase 2 (decisao do dono em 15/10/2026, executada em 18/10/2026). Ate aqui a
pergunta clinica ia ao Gemini 1.5 Pro e, em qualquer excecao, caia em
silencio para a OpenAI. Agora, com ANTHROPIC_API_KEY presente, o Claude
responde primeiro; os outros dois ficam como contingencia, e cada troca de
motor e cada recusa ficam no log.

O que se afirma aqui nao e o SDK — e o contrato desta casa sobre ele:

- a instrucao vai como bloco de sistema em cache, o prompt como mensagem;
- a profundidade e `effort`, e temperatura NAO e enviada (a API devolve 400);
- a pergunta clinica pede a contingencia de recusa da propria API; o passo
  de SQL do Data-FROID pede saida estruturada pelo esquema, sem contingencia;
- recusa vira texto vazio e o proximo motor assume, com o motivo no log;
- resposta cortada no teto de tokens se declara, nunca parece inteira;
- cada variavel nova tem a sua linha no docker-compose.yml, com o mesmo
  padrao de main.py, e o SDK esta pinado em requirements.txt.

O modulo `anthropic` e substituido por um dublê registrado em `sys.modules`:
nenhum teste aqui toca a rede.
"""

from __future__ import annotations

import asyncio
import re
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

import main  # noqa: E402

RAIZ = SERVIDOR.parent


def _resposta(texto="leitura clinica", parada="end_turn", modelo="claude-opus-5-5"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        stop_reason=parada,
        stop_details=None,
        model=modelo,
        usage=SimpleNamespace(
            input_tokens=1200,
            output_tokens=300,
            cache_read_input_tokens=900,
            cache_creation_input_tokens=0,
        ),
    )


class _Mensagens:
    def __init__(self, registro, beta):
        self._registro = registro
        self._beta = beta

    def create(self, **kwargs):
        self._registro["chamadas"].append({"beta": self._beta, **kwargs})
        efeito = self._registro.get("efeito")
        if isinstance(efeito, Exception):
            raise efeito
        return efeito if efeito is not None else _resposta()


class _ClienteFalso:
    registro = {"chamadas": [], "efeito": None, "clientes": []}

    def __init__(self, **kwargs):
        type(self).registro["clientes"].append(kwargs)
        self.messages = _Mensagens(type(self).registro, beta=False)
        self.beta = SimpleNamespace(messages=_Mensagens(type(self).registro, beta=True))


class _AuthenticationError(Exception):
    pass


def _modulo_falso():
    modulo = types.ModuleType("anthropic")
    modulo.Anthropic = _ClienteFalso
    modulo.AuthenticationError = _AuthenticationError
    return modulo


def _perguntar(**kwargs):
    return asyncio.run(
        main._generate_froid_explain_text("INSTRUCAO", "PROMPT", **kwargs)
    )


class OCaminhoClaude(unittest.TestCase):
    def setUp(self):
        _ClienteFalso.registro = {"chamadas": [], "efeito": None, "clientes": []}
        self._modulo_original = sys.modules.get("anthropic")
        sys.modules["anthropic"] = _modulo_falso()
        self._chaves = patch.multiple(
            main, ANTHROPIC_API_KEY="chave", GEMINI_API_KEY="g", OPENAI_API_KEY="o"
        )
        self._chaves.start()

    def tearDown(self):
        self._chaves.stop()
        if self._modulo_original is not None:
            sys.modules["anthropic"] = self._modulo_original
        else:
            sys.modules.pop("anthropic", None)

    def test_responde_primeiro_sem_passar_pelos_outros_motores(self):
        with self.assertNoLogs("froid.persistence", level="WARNING"):
            texto, motor = _perguntar(max_tokens=800, temperature=0.1)
        self.assertEqual(texto, "leitura clinica")
        self.assertEqual(motor, "Claude (claude-opus-5-5)")
        self.assertEqual(len(_ClienteFalso.registro["chamadas"]), 1)

    def test_a_pergunta_clinica_vai_com_cache_esforco_e_contingencia_de_recusa(self):
        _perguntar(max_tokens=800, temperature=0.1)
        chamada = _ClienteFalso.registro["chamadas"][0]
        self.assertTrue(chamada["beta"])
        self.assertEqual(chamada["model"], "claude-opus-5-5")
        # O teto dos outros motores (800) e so o piso aqui: o raciocinio conta
        # dentro de max_tokens, e com 800 a prova real de 18/10/2026 voltou vazia.
        self.assertEqual(chamada["max_tokens"], 16000)
        self.assertEqual(chamada["system"][0]["text"], "INSTRUCAO")
        self.assertEqual(chamada["system"][0]["cache_control"], {"type": "ephemeral"})
        # Revisao 20/10/2026, item 17: o prompt vai como bloco em cache, porque e
        # reenviado a cada turno de ferramenta.
        self.assertEqual(chamada["messages"], [{"role": "user", "content": [
            {"type": "text", "text": "PROMPT", "cache_control": {"type": "ephemeral"}}]}])
        self.assertEqual(chamada["output_config"], {"effort": "high"})
        self.assertEqual(chamada["fallbacks"], "default")
        self.assertEqual(chamada["betas"], ["server-side-fallback-2026-07-01"])
        self.assertNotIn("temperature", chamada)
        self.assertNotIn("thinking", chamada)

    def test_o_cliente_tem_teto_de_tempo_e_a_chave_do_ambiente(self):
        _perguntar(max_tokens=800)
        cliente = _ClienteFalso.registro["clientes"][0]
        self.assertEqual(cliente["api_key"], "chave")
        self.assertEqual(cliente["timeout"], 90.0)
        # Item 19: uma nova tentativa, nao duas — dentro do laco cada tentativa
        # repete um turno inteiro.
        self.assertEqual(cliente["max_retries"], 1)

    def test_o_passo_de_sql_pede_saida_estruturada_sem_contingencia(self):
        _ClienteFalso.registro["efeito"] = _resposta('{"result_sql": "SELECT 1", "cohort_sql": "SELECT 1"}')
        texto, _motor = _perguntar(
            max_tokens=500,
            temperature=0.0,
            json_mode=True,
            json_schema=main._ESQUEMA_SQL_DO_DATA_FROID,
        )
        chamada = _ClienteFalso.registro["chamadas"][0]
        self.assertFalse(chamada["beta"])
        self.assertNotIn("fallbacks", chamada)
        self.assertEqual(chamada["output_config"]["effort"], "high")
        self.assertEqual(chamada["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(
            chamada["output_config"]["format"]["schema"]["required"],
            ["result_sql", "cohort_sql"],
        )
        self.assertIn('"result_sql"', texto)

    def test_recusa_vira_texto_vazio_e_o_proximo_motor_assume_com_motivo_no_log(self):
        recusa = _resposta(texto="", parada="refusal")
        recusa.stop_details = SimpleNamespace(category="cyber", explanation="x")
        _ClienteFalso.registro["efeito"] = recusa
        with patch.multiple(main, GEMINI_API_KEY="", OPENAI_API_KEY=""):
            with self.assertLogs("froid.persistence", level="WARNING") as log:
                texto, motor = _perguntar(max_tokens=800)
        self.assertEqual((texto, motor), ("", "local-fallback"))
        self.assertTrue(any("Claude recusou (categoria=cyber)" in linha for linha in log.output))
        self.assertTrue(any("tentando o proximo motor" in linha for linha in log.output))

    def test_resposta_cortada_no_teto_se_declara(self):
        _ClienteFalso.registro["efeito"] = _resposta("comeco da leitura", parada="max_tokens")
        with self.assertLogs("froid.persistence", level="WARNING"):
            texto, _motor = _perguntar(max_tokens=800)
        self.assertTrue(texto.startswith("comeco da leitura"))
        self.assertIn("[resposta interrompida no teto de tokens", texto)

    def test_um_teto_maior_que_o_padrao_e_respeitado(self):
        _perguntar(max_tokens=20000)
        self.assertEqual(_ClienteFalso.registro["chamadas"][0]["max_tokens"], 20000)

    def test_raciocinio_que_consome_o_teto_sem_texto_fica_no_log(self):
        _ClienteFalso.registro["efeito"] = _resposta("", parada="max_tokens")
        with patch.multiple(main, GEMINI_API_KEY="", OPENAI_API_KEY=""):
            with self.assertLogs("froid.persistence", level="WARNING") as log:
                texto, _motor = _perguntar(max_tokens=800)
        self.assertEqual(texto, "")
        self.assertTrue(any("consumiu o teto de 16000 tokens" in linha for linha in log.output))

    def test_json_cortado_no_teto_nao_e_aproveitado(self):
        _ClienteFalso.registro["efeito"] = _resposta('{"result_sql": "SELE', parada="max_tokens")
        with patch.multiple(main, GEMINI_API_KEY="", OPENAI_API_KEY=""):
            with self.assertLogs("froid.persistence", level="WARNING"):
                texto, _motor = _perguntar(max_tokens=500, json_mode=True, json_schema={"type": "object"})
        self.assertEqual(texto, "")

    def test_falha_do_sdk_cai_para_o_proximo_motor_com_a_classe_no_log(self):
        _ClienteFalso.registro["efeito"] = _AuthenticationError("chave invalida")
        with patch.multiple(main, GEMINI_API_KEY="", OPENAI_API_KEY=""):
            with self.assertLogs("froid.persistence", level="WARNING") as log:
                texto, motor = _perguntar(max_tokens=800)
        self.assertEqual((texto, motor), ("", "local-fallback"))
        self.assertTrue(
            any("motor Claude (claude-opus-5-5) falhou com _AuthenticationError" in linha for linha in log.output)
        )

    def test_o_modelo_que_serviu_e_o_que_vai_no_nome_do_motor(self):
        # Com a contingencia de recusa da API, `response.model` pode ser outro
        # modelo; o log e a assinatura dizem qual serviu de fato.
        _ClienteFalso.registro["efeito"] = _resposta("ok", modelo="claude-opus-4-8")
        _texto, motor = _perguntar(max_tokens=800)
        self.assertEqual(motor, "Claude (claude-opus-4-8)")


class SemChaveNadaMuda(unittest.TestCase):
    def test_sem_chave_o_claude_nem_e_importado(self):
        sys.modules.pop("anthropic", None)
        with patch.multiple(main, ANTHROPIC_API_KEY="", GEMINI_API_KEY="", OPENAI_API_KEY=""):
            with self.assertLogs("froid.persistence", level="WARNING"):
                texto, motor = _perguntar(max_tokens=800)
        self.assertEqual((texto, motor), ("", "local-fallback"))


class AsVariaveisChegamAoConteiner(unittest.TestCase):
    """Armadilha 2.3: o servico recebe lista explicita, nao env_file."""

    def setUp(self):
        self.compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
        self.codigo = (SERVIDOR / "main.py").read_text(encoding="utf-8")
        self.requisitos = (SERVIDOR / "requirements.txt").read_text(encoding="utf-8")

    def _padrao_do_compose(self, nome):
        achado = re.search(rf"- {nome}=\$\{{{nome}:-([^}}]*)\}}", self.compose)
        self.assertIsNotNone(achado, f"{nome} nao esta no docker-compose.yml")
        return achado.group(1)

    def _padrao_do_codigo(self, nome):
        achado = re.search(rf'{nome} = (?:float\(|int\()?os\.getenv\("{nome}", "([^"]*)"\)', self.codigo)
        self.assertIsNotNone(achado, f"{nome} nao esta em main.py")
        return achado.group(1)

    def test_a_chave_tem_linha_no_compose(self):
        self.assertEqual(self._padrao_do_compose("ANTHROPIC_API_KEY"), "")

    def test_os_padroes_do_compose_sao_os_do_codigo(self):
        for nome in (
            "FROID_EXPLICA_CLAUDE_MODEL",
            "FROID_EXPLICA_CLAUDE_EFFORT",
            "FROID_EXPLICA_CLAUDE_TIMEOUT",
            "FROID_EXPLICA_CLAUDE_MAX_TOKENS",
        ):
            self.assertEqual(self._padrao_do_compose(nome), self._padrao_do_codigo(nome), nome)

    def test_o_modelo_padrao_e_o_opus_corrente(self):
        self.assertEqual(self._padrao_do_codigo("FROID_EXPLICA_CLAUDE_MODEL"), "claude-opus-5-5")

    def test_o_sdk_esta_pinado(self):
        self.assertRegex(self.requisitos, r"(?m)^anthropic==\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
