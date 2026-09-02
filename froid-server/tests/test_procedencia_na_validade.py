"""Um par de validade so vale se o lado do FROID tiver sido MEDIDO.

Em 02/09/2026 uma sessao real de 24 minutos rodou inteira com o motor em modo
simulado: o audio do paciente nunca chegou e os indices acusticos foram
gerados, nao medidos.

O detalhe que torna isso perigoso para um estudo de validade e este: dado
simulado tem cobertura e confianca EXCELENTES, porque e gerado limpo. Os dois
pisos que a funcao de pares ja aplicava o aprovariam sem hesitar. E o que a
tela envia como `prosodic_activation` e o IPM medio — numa sessao simulada, um
numero que o sistema inventou. Pareado com um PHQ-9 verdadeiro, ele fabrica
evidencia: sai coeficiente, intervalo e grafico, e nada por tras.

E o modo de falha mais caro possivel aqui, porque se agrava com o sucesso:
quanto mais dado se acumulasse, mais convincente ficaria o erro.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MIGRACAO = (SERVER_DIR / "migrations" / "030_procedencia_na_validade.sql").read_text(
    encoding="utf-8"
)
TENANT_STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")


class FuncaoDePares(unittest.TestCase):
    def test_a_coluna_de_procedencia_existe(self):
        self.assertIn("ADD COLUMN IF NOT EXISTS voice_measured_ratio", MIGRACAO)

    def test_os_pares_exigem_procedencia(self):
        self.assertIn("o.voice_measured_ratio >= 0.80", MIGRACAO)

    def test_procedencia_desconhecida_fica_de_FORA(self):
        """NULL nao pode ser permissivo aqui, e a diferenca e proposital.

        Cobertura e confianca tratam NULL como permissivo porque ali a ausencia
        e ruido de instrumentacao. Aqui a ausencia significa "coletado antes de
        a procedencia existir" — procedencia DESCONHECIDA, exatamente o caso
        que pode ter sido simulado. Incluir por omissao repetiria o defeito que
        esta migration fecha.
        """
        corpo = MIGRACAO[MIGRACAO.index("CREATE OR REPLACE FUNCTION") :]
        linha = [
            l for l in corpo.splitlines() if "voice_measured_ratio" in l and "AND" in l
        ]
        self.assertTrue(linha, "o filtro de procedencia sumiu da funcao")
        self.assertNotIn("IS NULL", linha[0])

    def test_os_filtros_antigos_continuam(self):
        # A procedencia ACRESCENTA uma dimensao; nao substitui as outras duas.
        self.assertIn("o.coverage IS NULL OR o.coverage >= 0.80", MIGRACAO)
        self.assertIn("o.confidence IS NULL OR o.confidence >= 0.70", MIGRACAO)
        self.assertIn("a.research_consent = TRUE", MIGRACAO)

    def test_a_assinatura_nao_mudou(self):
        # Mesmo contrato: quem chama a funcao nao precisa saber que ela ficou
        # mais exigente.
        self.assertIn(
            "RETURNS TABLE (pattern_value NUMERIC, instrument_score NUMERIC)", MIGRACAO
        )

    def test_a_migration_se_registra(self):
        self.assertIn("'030_procedencia_na_validade'", MIGRACAO)


class Gravacao(unittest.TestCase):
    def test_o_store_grava_a_procedencia(self):
        trecho = TENANT_STORE[
            TENANT_STORE.index("INSERT INTO validation_observations") :
        ][:900]
        self.assertIn("voice_measured_ratio", trecho)
        self.assertIn('obs.get("voice_measured_ratio")', trecho)


class Normalizacao(unittest.TestCase):
    """`_observacoes_com_procedencia`, sem subir o app inteiro.

    O modulo main importa o mundo; aqui interessa so a funcao, entao ela e
    extraida do fonte e avaliada isolada.
    """

    @classmethod
    def setUpClass(cls):
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        inicio = fonte.index("def _observacoes_com_procedencia")
        fim = fonte.index("\n@app.post", inicio)
        espaco = {}
        exec(compile(fonte[inicio:fim], "<extraido>", "exec"), espaco)
        cls.normalizar = staticmethod(espaco["_observacoes_com_procedencia"])

    def test_fracao_valida_atravessa(self):
        saida = self.normalizar([{"pattern_key": "ipm", "voice_measured_ratio": 0.93}])
        self.assertEqual(saida[0]["voice_measured_ratio"], 0.93)

    def test_ausente_vira_none_e_nao_zero(self):
        # Zero seria uma AFIRMACAO ("nada foi medido"); None e a duvida. Um
        # cliente desatualizado nao pode afirmar em nome de ninguem.
        saida = self.normalizar([{"pattern_key": "ipm"}])
        self.assertIsNone(saida[0]["voice_measured_ratio"])

    def test_fora_da_faixa_vira_none_e_nao_e_truncado(self):
        # Truncar inventaria uma procedencia que ninguem mediu.
        for valor in (1.4, -0.2, "muito", None, float("nan")):
            with self.subTest(valor=valor):
                saida = self.normalizar(
                    [{"pattern_key": "ipm", "voice_measured_ratio": valor}]
                )
                self.assertIsNone(saida[0]["voice_measured_ratio"])

    def test_extremos_legitimos_passam(self):
        for valor in (0.0, 1.0):
            with self.subTest(valor=valor):
                saida = self.normalizar(
                    [{"pattern_key": "ipm", "voice_measured_ratio": valor}]
                )
                self.assertEqual(saida[0]["voice_measured_ratio"], valor)

    def test_lixo_nao_derruba_a_gravacao(self):
        saida = self.normalizar([None, "texto", 7, {"pattern_key": "ok"}])
        self.assertEqual(len(saida), 1)
        self.assertEqual(saida[0]["pattern_key"], "ok")

    def test_nada_mais_e_alterado(self):
        entrada = {
            "pattern_key": "ipm",
            "pattern_value": 51.3,
            "coverage": 0.9,
            "voice_measured_ratio": 1.0,
        }
        saida = self.normalizar([entrada])[0]
        self.assertEqual(saida["pattern_value"], 51.3)
        self.assertEqual(saida["coverage"], 0.9)
        # E o dicionario de quem chamou continua intacto.
        self.assertEqual(len(entrada), 4)


class PisoEspelhado(unittest.TestCase):
    """O piso vive em dois lugares, e espelho de numero ja custou caro aqui.

    O SQL decide; a tela apenas avisa antes. Se os dois discordarem, o
    profissional e informado de uma regra que o banco nao aplica — e descobre a
    diferenca meses depois, quando o par nao aparece no estudo.
    """

    def test_o_piso_do_sql_e_o_da_tela_sao_o_mesmo(self):
        relatorio = (
            SERVER_DIR.parent
            / "froid-dashboard"
            / "src"
            / "pages"
            / "SessionReport.tsx"
        ).read_text(encoding="utf-8")
        do_sql = re.search(r"o\.voice_measured_ratio >= ([0-9.]+)", MIGRACAO)
        da_tela = re.search(r"PISO_DE_PROCEDENCIA = ([0-9.]+)", relatorio)
        self.assertIsNotNone(do_sql)
        self.assertIsNotNone(da_tela)
        self.assertEqual(float(do_sql.group(1)), float(da_tela.group(1)))

    def test_a_tela_aponta_para_a_fonte(self):
        relatorio = (
            SERVER_DIR.parent
            / "froid-dashboard"
            / "src"
            / "pages"
            / "SessionReport.tsx"
        ).read_text(encoding="utf-8")
        self.assertIn("030_procedencia_na_validade.sql", relatorio)


if __name__ == "__main__":
    unittest.main()
