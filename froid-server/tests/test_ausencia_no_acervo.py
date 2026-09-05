"""Ausencia chega ao acervo como ausencia, nunca como zero.

O CASO, e ele e a razao deste arquivo existir
---------------------------------------------
Num relatorio real de 04/09/2026 o paciente recebeu quatro paginas com VINTE E
UMA linhas em `0,00`. Nenhuma delas era uma medida de zero: o microfone nao
chegou a analise acustica e o motor devolveu `None` em todas, com honestidade.
Quem converteu foi a gravacao — `_safe_float(value, default=0.0)`.

`0,00` e a pior saida possivel para ausencia. E finito, alinha na coluna decimal
e tem duas casas: tipograficamente indistinguivel de uma medida real de zero.
Depois de gravado assim, o dado nao volta — o acervo nao guarda a origem.

A apresentacao ja foi corrigida (o PDF diz "nao medido nesta sessao" quando a
PROCEDENCIA diz que nao houve voz apurada). Este arquivo guarda a outra metade:
a causa raiz, na escrita.

POR QUE O TESTE E ESTATICO
--------------------------
`test_data_froid_privacy_runtime` exercita a gravacao de verdade e e pulado
inteiro sem `duckdb`, que e o caso da maquina de desenvolvimento. Um
`_safe_float` reintroduzido passaria por toda a bateria local e so apareceria em
producao, no fim de uma sessao real, gravando zero sobre silencio.

Por isso a varredura e pelo PARSER e pela REGRA — o arquivo inteiro, os quatro
comandos, todas as posicoes de valor — e nao pela ocorrencia que alguem viu.
Corrigir o lugar em vez da regra ja custou um incidente nesta casa.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MAIN_SRC = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
MAIN_TREE = ast.parse(MAIN_SRC)

# Os quatro comandos que escrevem no acervo anonimo.
COMANDOS_DO_ACERVO = (
    "INSERT INTO anonymous_session_cuts",
    "INSERT INTO anonymous_sessions",
    "UPDATE anonymous_sessions SET",
    "UPDATE anonymous_session_cuts SET",
)


def _chamadas_de_escrita():
    """Todo `conn.execute(...)` que grava numa das duas tabelas do acervo."""
    achadas = {}
    for no in ast.walk(MAIN_TREE):
        if not isinstance(no, ast.Call):
            continue
        if not (isinstance(no.func, ast.Attribute) and no.func.attr == "execute"):
            continue
        if not no.args or not isinstance(no.args[0], ast.Constant):
            continue
        sql = str(no.args[0].value)
        for marcador in COMANDOS_DO_ACERVO:
            if marcador in sql and marcador not in achadas:
                achadas[marcador] = no
    return achadas


def _colunas(sql: str, marcador: str):
    if marcador.startswith("INSERT"):
        corpo = sql[sql.index("(") + 1 : sql.index(")")]
        return [c.strip() for c in corpo.split(",") if c.strip()]
    return re.findall(r"(\w+)\s*=\s*\?", sql)


class OAcervoNaoRecebeZeroPorAusencia(unittest.TestCase):
    def setUp(self):
        self.chamadas = _chamadas_de_escrita()

    def test_os_quatro_comandos_existem(self):
        """Se um comando for renomeado, o teste precisa gritar em vez de passar
        vazio. Varredura que nao acha nada e indistinguivel de varredura limpa."""
        for marcador in COMANDOS_DO_ACERVO:
            self.assertIn(marcador, self.chamadas, f"nao achei: {marcador}")

    def test_nenhum_safe_float_grava_no_acervo(self):
        """A REGRA, varrida nas quatro listas de valores.

        `_safe_float` tem `default=0.0`. Em posicao de escrita ele transforma
        ausencia em zero, e zero gravado nao se distingue depois. Ele continua
        legitimo fora daqui (contagens, versoes, comparacoes internas); dentro
        de um valor que vai para o acervo, nao.
        """
        infratores = []
        for marcador, no in self.chamadas.items():
            if len(no.args) < 2 or not isinstance(no.args[1], ast.List):
                continue
            for coluna, valor in zip(_colunas(str(no.args[0].value), marcador), no.args[1].elts):
                fonte = ast.unparse(valor)
                if "_safe_float" in fonte:
                    infratores.append(f"{marcador} -> {coluna}: {fonte[:70]}")
        self.assertEqual(
            [],
            infratores,
            "ausencia viraria 0.0 no acervo em "
            + str(len(infratores))
            + " posicao(oes):\n  "
            + "\n  ".join(infratores),
        )

    def test_colunas_que_dependem_de_voz_nao_usam_conversor_com_queda(self):
        """`_safe_int` tem `default=0`, e para ESTAS colunas o zero mente.

        Contagem geralmente pode comecar em zero — `sample_count`,
        `session_duration`, `media_loss_events` sao contagens de verdade e
        continuam com `_safe_int`. As de baixo nao sao:

        `dissonance_count` so pode ser preenchida com voz apurada, porque
        `isReportableDissonance` exige `|deviation_score| > 1.5` e o desvio de
        zona vem do vetor espectral. Sem voz, o zero significa "nada foi
        avaliado", nunca "nenhuma dissonancia".

        `dominant_zone` e `baseline_zone` valem 1..12. Zero nao e uma zona — era
        um balde a mais no `GROUP BY` do Data-FROID, feito de ausencia.
        """
        proibidas = {"dissonance_count", "dominant_zone", "baseline_zone"}
        infratores = []
        for marcador, no in self.chamadas.items():
            if len(no.args) < 2 or not isinstance(no.args[1], ast.List):
                continue
            for coluna, valor in zip(_colunas(str(no.args[0].value), marcador), no.args[1].elts):
                if coluna not in proibidas:
                    continue
                fonte = ast.unparse(valor)
                if "_safe_int" in fonte or "_safe_float" in fonte:
                    infratores.append(f"{marcador} -> {coluna}: {fonte[:70]}")
        self.assertEqual([], infratores, "ausencia viraria 0 em:\n  " + "\n  ".join(infratores))

    def test_colunas_placeholders_e_valores_batem_nos_quatro(self):
        """Uma coluna a mais e um valor a menos passariam por toda a bateria
        local e so quebrariam em producao. Estendido aos quatro comandos: o
        teste anterior guardava so o INSERT dos cortes."""
        for marcador, no in self.chamadas.items():
            sql = str(no.args[0].value)
            colunas = _colunas(sql, marcador)
            self.assertGreater(len(no.args), 1, f"{marcador} sem lista de valores")
            self.assertIsInstance(no.args[1], ast.List, f"{marcador}: valores nao sao lista")
            n_valores = len(no.args[1].elts)
            n_placeholders = sql.count("?")
            self.assertEqual(len(colunas), n_placeholders, f"{marcador}: colunas != placeholders")
            self.assertEqual(len(colunas), n_valores, f"{marcador}: colunas != valores")


if __name__ == "__main__":
    unittest.main()
