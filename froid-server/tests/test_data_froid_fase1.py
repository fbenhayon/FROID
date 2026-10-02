"""Data-FROID, Fase 1: cada corte com a sua fala e o seu tema.

Desenho em `docs/data-froid-fase1-desenho.md`. O objetivo do dono (02/10/2026):
cada corte do acervo representa UM assunto tratado, com tema registrado, para o
FROID Explica consultar por tema. Quatro coisas impediam isso, e cada classe
abaixo trava uma:

- D1: `_transcript_for_range` devolvia a sessao inteira para todo corte;
- D2: o tema passava por lista fixa e virava `nao_classificado`;
- D3: o filtro de rotulos descartava rotulos do proprio sistema — so os
  favoraveis sobreviviam;
- D4/D5: o navegador mandava a categoria de intervencao antiga (que vencia a
  corrigida) e trechos literais do paciente fora da criptografia.
"""

import importlib.util
import re
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

REPO = SERVER_DIR.parent
LIVE_SESSION = REPO / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"
SESSION_REPORT = REPO / "froid-dashboard" / "src" / "lib" / "session-report.ts"

from froid_deidentify import (  # noqa: E402
    desidentificar_fala,
    desidentificar_tema,
    minusculas_da_sessao,
    nomes_da_sessao,
)

DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None

TRANSCRICAO = "\n".join(
    [
        "PC - Eu briguei com a Joana por causa do trabalho.",
        "DR. - Faz sentido voce sentir isso, compreendo o que aconteceu ali.",
        "PC - Ela foi embora para Itajuba e eu fiquei sozinho.",
        "PC - Tenho medo de dirigir na estrada e evito sair de casa.",
        "DR. - O que voce acha que aconteceria se fosse ate a esquina?",
    ]
)


def _normaliza(texto: str) -> str:
    sem = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", sem.lower()).strip("_")


class OTemaEDesidentificadoENaoApagado(unittest.TestCase):
    """D2. O tema e livre; o que sai dele e so o referencial."""

    def setUp(self):
        self.nomes = nomes_da_sessao(TRANSCRICAO)
        self.comuns = minusculas_da_sessao(TRANSCRICAO)

    def tema(self, texto):
        return desidentificar_tema(texto, self.nomes, self.comuns)

    def test_tema_comum_passa_intacto(self):
        self.assertEqual(self.tema("Medo de dirigir na estrada"), ("Medo de dirigir na estrada", "ok"))

    def test_nome_dito_na_sessao_sai_em_qualquer_posicao_e_caixa(self):
        self.assertEqual(self.tema("Joana e a separacao")[0], "[NOME] e a separacao")
        self.assertEqual(self.tema("conflito com joana")[0], "conflito com [NOME]")
        self.assertEqual(self.tema("Mudanca para Itajuba")[0], "Mudanca para [NOME]")

    def test_palavra_que_a_sessao_disse_em_minuscula_e_comum(self):
        """'Ansiedade no Trabalho' e 'Conflito com Pedro' tem a mesma forma; a
        sessao disse 'o trabalho', e nao disse 'pedro'."""
        self.assertEqual(self.tema("Ansiedade no Trabalho")[0], "Ansiedade no Trabalho")
        self.assertEqual(self.tema("Conflito com Pedro")[0], "Conflito com [NOME]")

    def test_sigla_e_vocabulario(self):
        self.assertEqual(self.tema("TCC e ansiedade")[0], "TCC e ansiedade")

    def test_data_e_identificador_estruturado_viram_marcador(self):
        self.assertEqual(self.tema("Luto desde marco")[0], "Luto desde [DATA]")
        self.assertEqual(self.tema("Ligacao 11 98765-4321")[0], "Ligacao [TELEFONE]")

    def test_toda_recusa_tem_motivo_e_devolve_vazio(self):
        self.assertEqual(self.tema(""), ("", "vazio"))
        self.assertEqual(self.tema("Joana Pedro"), ("", "referencial_demais"))
        self.assertEqual(self.tema(" ".join(["palavra"] * 13)), ("", "longo_demais"))

    def test_sem_transcricao_ainda_tira_maiuscula_fora_do_inicio(self):
        self.assertEqual(desidentificar_tema("Conversa com Marina")[0], "Conversa com [NOME]")


class OMarcadorNaoEReprocessadoComoNome(unittest.TestCase):
    """Defeito achado ao reaproveitar o modulo: `[DATA]` virava `[[NOME]]`."""

    def test_marcador_no_meio_do_periodo(self):
        texto, motivo = desidentificar_fala(
            "eu sugeri que voce anotasse isso no dia 12/05 para conversarmos depois com calma."
        )
        self.assertEqual(motivo, "ok")
        self.assertIn("[DATA]", texto)
        self.assertNotIn("[[", texto)

    def test_marcador_abrindo_o_periodo_nao_o_derruba(self):
        texto, motivo = desidentificar_fala(
            "12/05 foi o dia em que voce percebeu isso pela primeira vez, certo?"
        )
        self.assertEqual(motivo, "ok")
        self.assertTrue(texto.startswith("[DATA] foi o dia"), texto)


class ORecorteEDoCorte(unittest.TestCase):
    """D1. A fala de cada corte, e so a dele — ou a declaracao de que nao ha."""

    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def relatorio(self, segundos):
        return {"transcript": TRANSCRICAO, "transcriptLineSeconds": segundos}

    def test_cada_corte_recebe_so_as_suas_linhas(self):
        rel = self.relatorio([10, 40, 120, 320, 350])
        primeiro = self.main._transcript_for_range(rel, 0, 300)
        segundo = self.main._transcript_for_range(rel, 300, 600)
        self.assertEqual(len(primeiro.splitlines()), 3)
        self.assertEqual(len(segundo.splitlines()), 2)
        self.assertIn("estrada", segundo)
        self.assertNotIn("estrada", primeiro)

    def test_limite_e_o_mesmo_do_navegador(self):
        """`inicio <= segundo < fim`, como `collectTranscript`."""
        rel = self.relatorio([0, 300, 300, 599, 600])
        self.assertEqual(len(self.main._transcript_for_range(rel, 300, 600).splitlines()), 3)

    def test_corte_sem_fala_e_string_vazia_e_nao_None(self):
        rel = self.relatorio([10, 40, 120, 320, 350])
        self.assertEqual(self.main._transcript_for_range(rel, 600, 900), "")

    def test_sem_linha_do_tempo_nao_ha_recorte(self):
        self.assertIsNone(self.main._transcript_for_range({"transcript": TRANSCRICAO}, 0, 300))

    def test_linha_do_tempo_desalinhada_nao_ha_recorte(self):
        self.assertIsNone(self.main._transcript_for_range(self.relatorio([10, 40]), 0, 300))
        self.assertIsNone(
            self.main._transcript_for_range(self.relatorio([10, 40, None, 320, 350]), 0, 300)
        )


class OsRotulosDoSistemaSobrevivem(unittest.TestCase):
    """D3. Todo rotulo que o sistema emite chega ao acervo como foi emitido."""

    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def test_cada_rotulo_da_tabela_sobrevive_ao_filtro(self):
        for rotulo in self.main.ROTULOS_EMITIDOS_PELO_SISTEMA:
            with self.subTest(rotulo=rotulo):
                self.assertEqual(self.main._anonymous_category(rotulo, "<<DESCARTADO>>"), rotulo)

    def test_os_desfavoraveis_que_sumiam(self):
        for emitido, esperado in (
            ("piora", "piora"),
            ("oscilante", "oscilante"),
            ("primeira_sessao", "primeira_sessao"),
            ("estável", "estavel"),
            ("início", "inicio"),
            ("redução", "reducao"),
            ("automatico_10min", "automatico_10min"),
        ):
            with self.subTest(emitido=emitido):
                self.assertEqual(self.main._anonymous_category(emitido, "x"), esperado)

    def test_nenhum_rotulo_da_tabela_e_inventado(self):
        """Cada entrada tem de existir como literal no navegador ou no servidor;
        rotulo que ninguem emite e porta aberta sem motivo."""
        fontes = LIVE_SESSION.read_text(encoding="utf-8") + (SERVER_DIR / "main.py").read_text(
            encoding="utf-8"
        )
        literais = {_normaliza(m) for m in re.findall(r'"([^"\n]{1,40})"', fontes)}
        for rotulo in self.main.ROTULOS_EMITIDOS_PELO_SISTEMA:
            with self.subTest(rotulo=rotulo):
                self.assertIn(rotulo, literais)

    def test_texto_livre_continua_barrado_pelo_filtro(self):
        self.assertEqual(self.main._anonymous_category("joana foi embora", "x"), "x")


class ONavegadorMandaALinhaDoTempoENaoOLiteral(unittest.TestCase):
    """D4 e D5, no contrato do relatorio."""

    @classmethod
    def setUpClass(cls):
        cls.live = LIVE_SESSION.read_text(encoding="utf-8")
        cls.tipo = SESSION_REPORT.read_text(encoding="utf-8")

    def test_relatorio_leva_a_linha_do_tempo(self):
        self.assertRegex(
            self.live,
            r"transcriptLineSeconds: transcriptSegmentsRef\.current\.map\(\s*\(segment\) => segment\.elapsedSeconds",
        )
        self.assertRegex(self.live, r"transcript: summarySourceTranscript,")
        self.assertIn("transcriptLineSeconds?: number[];", self.tipo)

    def test_contexto_anonimo_nao_carrega_fala_nem_categoria(self):
        for campo in ("patientSummaryAnon", "professionalSummaryAnon", "interventionCategory"):
            with self.subTest(campo=campo):
                self.assertNotRegex(self.live, campo + r"\s*:")
                self.assertNotRegex(self.tipo, campo + r"\??\s*:")

    def test_o_servidor_nao_le_a_categoria_do_navegador(self):
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        self.assertNotIn('cut_context.get("interventionCategory")', fonte)
        self.assertNotIn('cut_context.get("intervention_category")', fonte)


@unittest.skipUnless(DUCKDB_AVAILABLE, "duckdb e instalado na imagem do backend")
class AGravacaoDeVerdade(unittest.TestCase):
    """O acervo gravado, lido de volta do DuckDB."""

    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def _relatorio(self, *, com_linha_do_tempo=True):
        rel = {
            "sessionId": "sessao-fase1",
            "createdAt": "2026-10-02T10:00:00+00:00",
            "durationSeconds": 900,
            "transcript": TRANSCRICAO,
            "sessionAverage": {},
            "baseline": {},
            "sessionSummary": {"theme": "Conflito com Joana e medo"},
            "conversationSummaries": [
                {"startSecond": 0, "endSecond": 300, "startMinute": 0, "endMinute": 5,
                 "theme": "Conflito com Joana no trabalho"},
                {"startSecond": 300, "endSecond": 600, "startMinute": 5, "endMinute": 10,
                 "theme": "Medo de dirigir na estrada"},
            ],
            "tenMinuteCuts": [
                {"startSecond": 0, "endSecond": 300, "sampleCount": 30, "theme": "briguei joana trabalho"},
                {"startSecond": 300, "endSecond": 600, "sampleCount": 30, "theme": "medo dirigir estrada"},
                {"startSecond": 600, "endSecond": 900, "sampleCount": 30, "theme": ""},
            ],
            "anonymizedContext": {
                "sessionModality": "remote",
                "sessionKind": "primeira_sessao",
                # O navegador antigo mandava isto; o servidor nao pode obedecer.
                "cuts": [{"interventionCategory": "pergunta_aberta"}] * 3,
            },
        }
        if com_linha_do_tempo:
            rel["transcriptLineSeconds"] = [10, 40, 120, 320, 350]
        return rel

    def _gravar(self, relatorio):
        import duckdb

        pasta = tempfile.mkdtemp()
        caminho = str(Path(pasta) / "acervo.duckdb")
        with patch.object(self.main, "FROID_DUCKDB_PATH", caminho), patch.object(
            self.main, "FROID_DATAMART_PSEUDONYM_KEY", "k" * 40
        ):
            self.main._append_anonymous_datamart_row(relatorio)
        conn = duckdb.connect(caminho, read_only=True)
        # A gravacao engole excecao e manda para quarentena: sem conferir a
        # auditoria, um erro aqui passaria como sucesso.
        auditoria = conn.execute("SELECT accepted, reason FROM privacy_ingestion_audit").fetchall()
        self.assertEqual(auditoria, [(True, "approved")])
        return conn

    def _cortes(self, conn):
        colunas = [
            "cut_index", "transcript_scope", "patient_word_count", "professional_word_count",
            "speech_density", "intervention_category", "theme_predominant", "theme_deid_reason",
            "theme", "patient_summary_anon", "cut_context_json",
        ]
        linhas = conn.execute(
            f"SELECT {', '.join(colunas)} FROM anonymous_session_cuts ORDER BY cut_index"
        ).fetchall()
        return [dict(zip(colunas, linha)) for linha in linhas]

    def test_cada_corte_grava_a_sua_fala_e_o_seu_tema(self):
        conn = self._gravar(self._relatorio())
        cortes = self._cortes(conn)
        self.assertEqual(len(cortes), 3)
        primeiro, segundo, terceiro = cortes

        self.assertEqual([c["transcript_scope"] for c in cortes], ["corte"] * 3)
        # As contagens sao DO CORTE: antes, os tres cortes repetiam as da sessao.
        self.assertGreater(primeiro["patient_word_count"], 0)
        self.assertGreater(primeiro["professional_word_count"], 0)
        self.assertGreater(segundo["patient_word_count"], 0)
        self.assertNotEqual(primeiro["patient_word_count"], segundo["patient_word_count"])
        self.assertEqual((terceiro["patient_word_count"], terceiro["professional_word_count"]), (0, 0))

        # Categoria do classificador do servidor, sobre a fala DR. do corte —
        # nao o "pergunta_aberta" que o contexto do navegador trazia.
        self.assertEqual(primeiro["intervention_category"], "validacao_emocional")
        self.assertEqual(terceiro["intervention_category"], "sem_fala_profissional")

        # O tema da IA, desidentificado, e a chave de consulta.
        self.assertEqual(primeiro["theme_predominant"], "Conflito com [NOME] no trabalho")
        self.assertEqual(segundo["theme_predominant"], "Medo de dirigir na estrada")
        self.assertEqual(primeiro["theme_deid_reason"], "ok")
        self.assertNotIn("joana", (primeiro["theme"] or "").lower())

        # A fala do paciente continua fora, em qualquer coluna.
        for corte in cortes:
            self.assertEqual(corte["patient_summary_anon"], "")
            self.assertNotIn("briguei com a", corte["cut_context_json"].lower())

        sessao = conn.execute(
            "SELECT session_modality, session_kind, summary_theme, summary_theme_deid_reason "
            "FROM anonymous_sessions"
        ).fetchone()
        self.assertEqual(sessao, ("remote", "primeira_sessao", "Conflito com [NOME] e medo", "ok"))
        conn.close()

    def test_sem_linha_do_tempo_o_corte_declara_que_nao_recortou(self):
        conn = self._gravar(self._relatorio(com_linha_do_tempo=False))
        for corte in self._cortes(conn):
            with self.subTest(corte=corte["cut_index"]):
                self.assertEqual(corte["transcript_scope"], "sem_linha_do_tempo")
                self.assertIsNone(corte["patient_word_count"])
                self.assertIsNone(corte["professional_word_count"])
                self.assertIsNone(corte["speech_density"])
                self.assertEqual(corte["intervention_category"], "sem_recorte_temporal")
        conn.close()


if __name__ == "__main__":
    unittest.main()
