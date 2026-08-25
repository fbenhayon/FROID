"""Nenhum NameError esperando o usuario certo passar pela linha errada.

Este arquivo nasceu de dois defeitos reais, encontrados no mesmo dia:

1. `is_clinic` em tenant_store._organization_for_email. A linha que DEFINIA o
   nome foi removida num commit que reescreveu o calculo do id da organizacao;
   a linha que o USAVA ficou. Como a unica chamada esta dentro de um
   `except Exception` que apenas registra no log, o cadastro continuou
   respondendo 200 e o espelho em PostgreSQL parou de receber organizacao,
   usuario e vinculo. O modulo NR-1 inteiro vive nesse espelho, entao TODO
   link do NR-1 passou a devolver "permissao organizacional insuficiente" —
   um sintoma a tres camadas de distancia da causa.

2. `_persist_state` em main.set_patient_results_access. Nunca existiu: entrou
   com esse nome. O endpoint mudava PATIENTS em memoria e so entao estourava,
   entao a liberacao de resultado ao paciente valia ate o restart seguinte.

O que os dois tem em comum nao e o descuido, e a INVISIBILIDADE. O modulo
importa, a suite passa, o container sobe saudavel. Teste que exercita o caminho
feliz nao chega la, e `except Exception` transforma o estouro em silencio.

A varredura e estatica de proposito: nao precisa de banco, de rede nem de
fixture, e cobre os caminhos que nenhum teste exercita — que sao exatamente
onde este defeito se esconde.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from nomes_orfaos import orfaos  # noqa: E402

# Todo modulo que o servidor importa em tempo de execucao. Ferramenta em
# tools/ fica de fora: ela roda na mao e o erro aparece na hora.
MODULOS_DE_RUNTIME = (
    "main.py",
    "tenant_store.py",
    "nr1_compliance.py",
    "nr1_effectiveness.py",
    "legal_documents.py",
    "lgpd_registry.py",
)


class NenhumNomeIndefinido(unittest.TestCase):
    def test_nenhum_modulo_de_runtime_carrega_nome_que_nao_existe(self):
        achados = []
        for nome in MODULOS_DE_RUNTIME:
            caminho = SERVER_DIR / nome
            if not caminho.exists():
                continue
            for _dono, linha, identificador in sorted(set(orfaos(caminho))):
                achados.append(f"{nome}:{linha} -> '{identificador}'")
        self.assertEqual(
            achados,
            [],
            "nome carregado sem existir em escopo algum (NameError em tempo de "
            "execucao):\n  " + "\n  ".join(achados),
        )

    def test_a_varredura_realmente_pega_o_defeito_que_a_motivou(self):
        """Verificador que nao acusa nada nunca e verificador que nao funciona.

        Reproduz os dois defeitos originais em codigo de mentira. Sem isto, um
        analisador quebrado passaria como suite verde para sempre.
        """
        import ast
        import tempfile

        casos = (
            # o de tenant_store: definicao removida, uso preservado
            "def grava(perfil, email):\n"
            "    documento = perfil.get('doc')\n"
            "    return None if is_clinic else email\n",
            # o de main: funcao que nunca existiu
            "def libera(paciente):\n"
            "    paciente['ok'] = True\n"
            "    _persist_state()\n",
        )
        for fonte in casos:
            with self.subTest(fonte=fonte.splitlines()[0]):
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".py", delete=False, encoding="utf-8"
                ) as arquivo:
                    arquivo.write(fonte)
                    caminho = Path(arquivo.name)
                try:
                    ast.parse(fonte)
                    self.assertTrue(orfaos(caminho), "a varredura nao acusou o defeito")
                finally:
                    caminho.unlink(missing_ok=True)

    def test_a_varredura_nao_acusa_o_que_e_legitimo(self):
        """Falso positivo custa mais caro que o defeito: ensina a ignorar o teste.

        Fecho, comprehension, `global`, argumento so-nomeado, excecao nomeada e
        atributo de classe sao os casos em que um analisador ingenuo erra.
        """
        import tempfile

        legitimo = (
            "import os\n"
            "TOTAL = 0\n"
            "def externa(itens, *extras, chave=None, **resto):\n"
            "    acumulado = []\n"
            "    def interna():\n"
            "        return acumulado, chave, itens\n"
            "    filtrados = [i for i in itens if i]\n"
            "    mapa = {k: v for k, v in resto.items()}\n"
            "    try:\n"
            "        os.stat('x')\n"
            "    except OSError as erro:\n"
            "        return erro, filtrados, mapa, extras\n"
            "    global TOTAL\n"
            "    TOTAL = len(filtrados)\n"
            "    return interna(), TOTAL, __file__\n"
            "class Coisa:\n"
            "    campo = 1\n"
            "    def usa(self):\n"
            "        return self.campo, TOTAL\n"
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as arquivo:
            arquivo.write(legitimo)
            caminho = Path(arquivo.name)
        try:
            self.assertEqual(list(orfaos(caminho)), [])
        finally:
            caminho.unlink(missing_ok=True)


class OEspelhoNaoPodeFalharEmSilencio(unittest.TestCase):
    """A organizacao no PostgreSQL nasce da sincronizacao, e so dela.

    _organization_for_email e chamada exclusivamente de dentro de sync_all, que
    por sua vez so e chamada por _mirror_legacy_state_to_postgres — dentro de um
    `except Exception` que registra e segue. Quer dizer: qualquer falha ali
    deixa o cadastro respondendo 200 com o PostgreSQL vazio, e o NR-1 inteiro,
    que vive no PostgreSQL, para de funcionar sem que nada acuse.
    """

    def test_a_regra_do_cnpj_mora_num_lugar_so(self):
        """Foi a copia dessa regra, removida de um lado so, que gerou o defeito."""
        from tenant_store import (
            organization_derives_from_cnpj,
            organization_id_for_profile,
            stable_uuid,
        )

        # Onde a funcao diz "vem do CNPJ", o id precisa de fato vir do CNPJ.
        for tipo, documento in (
            ("organization", "12345678000199"),
            ("nr1_company", "12.345.678/0001-99"),
        ):
            with self.subTest(tipo=tipo):
                self.assertTrue(organization_derives_from_cnpj(tipo, documento))
                self.assertEqual(
                    organization_id_for_profile("a@b.com", tipo, documento),
                    stable_uuid("organization", "cnpj", "12345678000199"),
                )

        # E onde diz que nao, o id vem do e-mail — inclusive quando o tipo e de
        # empresa mas o documento ainda nao foi informado.
        for tipo, documento in (
            ("individual", ""),
            ("individual", "12345678000199"),
            ("organization", ""),
            ("nr1_company", None),
        ):
            with self.subTest(tipo=tipo, documento=documento):
                self.assertFalse(organization_derives_from_cnpj(tipo, documento))
                self.assertEqual(
                    organization_id_for_profile("a@b.com", tipo, documento),
                    stable_uuid("organization", "a@b.com"),
                )

    def test_organizacao_de_cnpj_nao_reivindica_o_email_do_titular(self):
        """legacy_owner_email tem indice unico, e a colisao e silenciosa.

        A mesma pessoa pode ter organizacao propria (autonomo, derivada do
        e-mail) e aparecer numa organizacao de CNPJ — a clinica em que atua, ou
        a empresa dela no NR-1. Se as duas linhas reivindicarem o mesmo e-mail,
        a segunda estoura com UniqueViolation dentro do mesmo `except` que
        engoliu o NameError, e o efeito visivel e identico: PostgreSQL sem a
        organizacao e NR-1 recusando todo mundo.
        """
        fonte = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def _organization_for_email"):]
        trecho = trecho[: trecho.index("INSERT INTO users")]
        self.assertIn("organization_derives_from_cnpj(", trecho)
        self.assertIn("else owner_email", trecho)
        # E a condicao nao pode voltar a ser escrita a mao aqui.
        self.assertNotIn("account_type_raw == \"organization\"", trecho)

    def test_a_falha_do_espelho_continua_sendo_registrada(self):
        """Engolir a excecao e decisao deliberada; engolir em silencio nao.

        A gravacao legada e a autoritativa e nao pode ser desfeita porque o
        espelho falhou — mas o log tem de contar, senao a proxima falha custa
        os mesmos dias.
        """
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        trecho = fonte[fonte.index("def _mirror_legacy_state_to_postgres"):]
        trecho = trecho[: trecho.index("\n\n\n")]
        self.assertIn("LOGGER.exception", trecho)


if __name__ == "__main__":
    unittest.main()
