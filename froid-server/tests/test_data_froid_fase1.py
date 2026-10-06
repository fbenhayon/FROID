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

A auditoria de 05/10/2026 acrescentou o que esta marcado como "auditoria":
o vocabulario da sessao por MAIORIA (um deslize do transcritor nao libera um
nome; um nome que so abre frase nao escapa), a segunda leitura do tema, o
gatilho do corte lido do resumo, o nome da zona em `dominant_theme`, a era v5
e o carimbo de tempo da fala no INICIO do bloco de audio.
"""

import ast
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
    VERSAO_DEID,
    desidentificar_fala,
    desidentificar_tema,
    vocabulario_da_sessao,
)

DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None

# Uma sessao pequena com as situacoes que a limpeza do tema precisa resolver:
# - "Joana": nome no MEIO de frase (2x), e um deslize do transcritor em
#   minuscula (1x) — a maioria decide, e ela e nome;
# - "Marcos": nome que SO abre frase (2x), nunca em minuscula;
# - "trabalho": dito em minuscula (2x) e abrindo frase (1x) — palavra comum;
# - "Clara": nome (1x no meio) e adjetivo "clara" (1x) — empate, e nome;
# - "Consigo": verbo abrindo frase, nunca em minuscula — nao pode virar nome;
# - "TCC": sigla.
TRANSCRICAO = "\n".join(
    [
        "PC - Eu briguei com a Joana por causa do trabalho.",
        "DR. - Faz sentido voce sentir isso, compreendo o que aconteceu ali.",
        "PC - Ela foi embora para Itajuba e eu fiquei sozinho. Trabalho e tudo pra mim.",
        "PC - Marcos nao ligou. Marcos nunca liga, e a joana tambem nao.",
        "DR. - E como voce se sentiu com a Joana indo embora? A Clara disse algo?",
        "PC - A conversa foi clara. Consigo dormir pouco por causa do trabalho.",
        "PC - Tenho medo de dirigir na estrada e evito sair de casa. A TCC ajudou.",
        "DR. - O que voce acha que aconteceria se fosse ate a esquina?",
    ]
)


def _normaliza(texto: str) -> str:
    sem = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", sem.lower()).strip("_")


def _fonte_da_funcao(nome: str) -> str:
    src = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
    for no in ast.parse(src).body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return ast.get_source_segment(src, no) or ""
    raise AssertionError(f"nao achei {nome}")


class OVocabularioDaSessaoDecidePorMaioria(unittest.TestCase):
    """auditoria — as duas frestas da primeira versao."""

    @classmethod
    def setUpClass(cls):
        cls.vocab = vocabulario_da_sessao(TRANSCRICAO)

    def test_nome_no_meio_de_frase_e_nome(self):
        self.assertIn("joana", self.vocab.nomes)
        self.assertIn("itajuba", self.vocab.nomes)
        self.assertIn("clara", self.vocab.nomes)

    def test_um_deslize_do_transcritor_nao_libera_o_nome(self):
        """'joana' em minuscula uma vez, 'Joana' no meio duas: continua nome."""
        self.assertIn("joana", self.vocab.nomes)
        self.assertNotIn("joana", self.vocab.comuns)

    def test_nome_que_so_abre_frase_entra_como_inicial(self):
        self.assertIn("marcos", self.vocab.iniciais)
        self.assertNotIn("marcos", self.vocab.nomes)

    def test_palavra_comum_capitalizada_por_posicao_e_comum(self):
        self.assertIn("trabalho", self.vocab.comuns)
        self.assertNotIn("trabalho", self.vocab.iniciais)

    def test_verbo_de_abertura_e_sigla_nao_viram_nome(self):
        for chave in ("consigo", "tenho", "tcc", "faz", "e"):
            with self.subTest(chave=chave):
                self.assertNotIn(chave, self.vocab.nomes | self.vocab.iniciais)

    def test_sem_transcricao_o_vocabulario_e_vazio(self):
        vazio = vocabulario_da_sessao("")
        self.assertEqual((frozenset(), frozenset(), frozenset()), (vazio.nomes, vazio.iniciais, vazio.comuns))


class OTemaEDesidentificadoENaoApagado(unittest.TestCase):
    """D2. O tema e livre; o que sai dele e so o referencial."""

    @classmethod
    def setUpClass(cls):
        cls.vocab = vocabulario_da_sessao(TRANSCRICAO)

    def tema(self, texto):
        return desidentificar_tema(texto, self.vocab)

    def test_tema_comum_passa_intacto(self):
        self.assertEqual(self.tema("Medo de dirigir na estrada"), ("Medo de dirigir na estrada", "ok"))

    def test_nome_dito_na_sessao_sai_em_qualquer_posicao_e_caixa(self):
        self.assertEqual(self.tema("Joana e a separacao")[0], "[NOME] e a separacao")
        self.assertEqual(self.tema("conflito com joana")[0], "conflito com [NOME]")
        self.assertEqual(self.tema("Mudanca para Itajuba")[0], "Mudanca para [NOME]")

    def test_nome_que_so_abre_frase_tambem_sai(self):
        """auditoria — 'Marcos' nunca apareceu no meio de frase na sessao."""
        self.assertEqual(self.tema("Marcos e o silencio")[0], "[NOME] e o silencio")
        self.assertEqual(self.tema("silencio de marcos")[0], "silencio de [NOME]")

    def test_palavra_que_a_sessao_disse_em_minuscula_e_comum(self):
        """'Ansiedade no Trabalho' e 'Conflito com Pedro' tem a mesma forma; a
        sessao disse 'trabalho' em minuscula, e nao disse 'pedro'."""
        self.assertEqual(self.tema("Ansiedade no Trabalho")[0], "Ansiedade no Trabalho")
        self.assertEqual(self.tema("Conflito com Pedro")[0], "Conflito com [NOME]")

    def test_verbo_de_abertura_fica(self):
        self.assertEqual(self.tema("Nao consigo dormir")[0], "Nao consigo dormir")

    def test_sigla_e_vocabulario(self):
        self.assertEqual(self.tema("TCC e ansiedade")[0], "TCC e ansiedade")

    def test_data_e_identificador_estruturado_viram_marcador(self):
        self.assertEqual(self.tema("Luto desde marco")[0], "Luto desde [DATA]")
        self.assertEqual(self.tema("Ligacao 11 98765-4321")[0], "Ligacao [TELEFONE]")

    def test_segunda_leitura_recusa_digito_que_escapou(self):
        """auditoria — 'covid19' nao casa `\\b\\d+\\b`; sobrou digito, cai."""
        self.assertEqual(self.tema("Sequelas da covid19"), ("", "referencial_demais"))

    def test_toda_recusa_tem_motivo_e_devolve_vazio(self):
        self.assertEqual(self.tema(""), ("", "vazio"))
        self.assertEqual(self.tema("Joana Marcos"), ("", "referencial_demais"))
        self.assertEqual(self.tema(" ".join(["palavra"] * 13)), ("", "longo_demais"))

    def test_sem_vocabulario_ainda_tira_maiuscula_fora_do_inicio(self):
        self.assertEqual(desidentificar_tema("Conversa com Marina")[0], "Conversa com [NOME]")

    def test_a_versao_da_limpeza_subiu_com_a_regra(self):
        self.assertEqual("deid-v2", VERSAO_DEID)


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
    """D1. A fala de cada corte, e so a dela — ou a declaracao de que nao ha."""

    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def relatorio(self, segundos):
        return {"transcript": TRANSCRICAO, "transcriptLineSeconds": segundos}

    def test_cada_corte_recebe_so_as_suas_linhas(self):
        rel = self.relatorio([10, 40, 120, 200, 250, 320, 350, 400])
        primeiro = self.main._transcript_for_range(rel, 0, 300)
        segundo = self.main._transcript_for_range(rel, 300, 600)
        self.assertEqual(len(primeiro.splitlines()), 5)
        self.assertEqual(len(segundo.splitlines()), 3)
        self.assertIn("estrada", segundo)
        self.assertNotIn("estrada", primeiro)

    def test_limite_e_o_mesmo_do_navegador(self):
        """`inicio <= segundo < fim`, como `collectTranscript`."""
        rel = self.relatorio([0, 300, 300, 599, 600, 700, 800, 900])
        self.assertEqual(len(self.main._transcript_for_range(rel, 300, 600).splitlines()), 3)

    def test_corte_sem_fala_e_string_vazia_e_nao_None(self):
        rel = self.relatorio([10, 40, 120, 200, 250, 320, 350, 400])
        self.assertEqual(self.main._transcript_for_range(rel, 600, 900), "")

    def test_sem_linha_do_tempo_nao_ha_recorte(self):
        self.assertIsNone(self.main._transcript_for_range({"transcript": TRANSCRICAO}, 0, 300))

    def test_linha_do_tempo_desalinhada_nao_ha_recorte(self):
        self.assertIsNone(self.main._transcript_for_range(self.relatorio([10, 40]), 0, 300))
        self.assertIsNone(
            self.main._transcript_for_range(self.relatorio([10, 40, None, 200, 250, 320, 350, 400]), 0, 300)
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
            ("manual", "manual"),
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

    def test_o_nome_da_zona_vira_rotulo_e_nao_nao_classificado(self):
        """auditoria — `dominant_theme` gravava `nao_classificado` em TODA linha."""
        self.assertEqual("tristeza_vs_paz_interior", self.main._rotulo_da_zona(3))
        self.assertIsNone(self.main._rotulo_da_zona(None))
        self.assertIsNone(self.main._rotulo_da_zona(0))
        self.assertIsNone(self.main._rotulo_da_zona(13))
        rotulos = {self.main._rotulo_da_zona(z) for z in range(1, 13)}
        self.assertEqual(12, len(rotulos))
        self.assertTrue(all(r and re.fullmatch(r"[a-z0-9_]+", r) for r in rotulos), rotulos)


class ONavegadorMandaALinhaDoTempoENaoOLiteral(unittest.TestCase):
    """D4 e D5, no contrato do relatorio — e os acertos da auditoria."""

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

    def test_a_fala_e_carimbada_no_inicio_do_bloco_de_audio(self):
        """auditoria — carimbar na chegada do texto empurrava a fala ~10 s."""
        self.assertIn("startedAtSecond ?? elapsedSecondsRef.current", self.live)
        self.assertIn("segmentStartedAtSecond = Math.max(0, elapsedSecondsRef.current);", self.live)
        self.assertRegex(self.live, r"segmentSpeaker,\s*segmentStartedAtSecond,\s*\)")
        self.assertIn("appendTranscriptText(text, speaker, startedAtSecond);", self.live)

    def test_o_ultimo_corte_nao_se_compara_com_ele_mesmo(self):
        """auditoria — `nextReference = nextCut || cut` gravava delta 0 e
        'estabilidade' sobre um depois que nao existe."""
        self.assertNotIn("const nextReference", self.live)
        self.assertNotIn("nextReference.", self.live)
        for campo in ("ipmDeltaAfterIntervention", "idmDeltaAfterIntervention"):
            with self.subTest(campo=campo):
                self.assertRegex(self.live, campo + r": nextCut \? rounded\(")
        self.assertRegex(self.live, r"responseIpmDirection: deltaDirection\(nextCut \? menos\(")

    def test_o_gatilho_e_o_tema_vem_do_resumo_do_corte(self):
        self.assertRegex(self.live, r"cutTrigger:\s*summary\?\.trigger \?\?")
        self.assertIn('themePredominant: summary?.theme ? limitTheme(summary.theme, 6) : "",', self.live)
        self.assertIn("conversationSummaries.find((item) => item.startSecond === cut.startSecond)", self.live)


class AIngestaoNaoBloqueiaOServidor(unittest.TestCase):
    """auditoria — um worker so; a gravacao corria dentro do laco de eventos."""

    def test_a_gravacao_corre_fora_do_laco_de_eventos(self):
        fonte = _fonte_da_funcao("save_session_report")
        self.assertIn("await asyncio.to_thread(_append_anonymous_datamart_row, report)", fonte)
        self.assertNotRegex(fonte, r"^\s*_append_anonymous_datamart_row\(report\)", )

    def test_a_gravacao_e_serializada_por_uma_trava(self):
        fonte = _fonte_da_funcao("_append_anonymous_datamart_row")
        self.assertIn("with _TRAVA_DO_ACERVO:", fonte)

    def test_o_esquema_e_lido_uma_vez_por_tabela(self):
        fonte = _fonte_da_funcao("_ensure_duckdb_columns")
        # Conta a CHAMADA, nao a mencao na docstring.
        self.assertEqual(1, fonte.count('execute(f"PRAGMA table_info'))
        src = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("def _ensure_duckdb_column(", src)


@unittest.skipUnless(DUCKDB_AVAILABLE, "duckdb e instalado na imagem do backend")
class AGravacaoDeVerdade(unittest.TestCase):
    """O acervo gravado, lido de volta do DuckDB."""

    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def _relatorio(self, *, com_linha_do_tempo=True, com_tema_da_sessao=True):
        rel = {
            "sessionId": "sessao-fase1",
            "createdAt": "2026-10-02T10:00:00+00:00",
            "durationSeconds": 900,
            "transcript": TRANSCRICAO,
            "sessionAverage": {"theme": "joana trabalho embora marcos"},
            "baseline": {},
            "sessionSummary": {"theme": "Conflito com Joana e medo"} if com_tema_da_sessao else {},
            "conversationSummaries": [
                {"startSecond": 0, "endSecond": 300, "startMinute": 0, "endMinute": 5,
                 "theme": "Conflito com Joana no trabalho", "trigger": "manual"},
                {"startSecond": 300, "endSecond": 600, "startMinute": 5, "endMinute": 10,
                 "theme": "Medo de dirigir na estrada", "trigger": "automatico_10min"},
            ],
            "tenMinuteCuts": [
                {"startSecond": 0, "endSecond": 300, "sampleCount": 30, "theme": "briguei joana trabalho",
                 "dominantZone": 3},
                {"startSecond": 300, "endSecond": 600, "sampleCount": 30, "theme": "medo dirigir estrada",
                 "dominantZone": 8},
                {"startSecond": 600, "endSecond": 900, "sampleCount": 30, "theme": "marcos liga"},
            ],
            "anonymizedContext": {
                "sessionModality": "remote",
                "sessionKind": "primeira_sessao",
                # O navegador antigo mandava isto; o servidor nao pode obedecer.
                "cuts": [{"interventionCategory": "pergunta_aberta", "cutTrigger": "automatico_10min"}] * 3,
            },
        }
        if com_linha_do_tempo:
            rel["transcriptLineSeconds"] = [10, 40, 120, 200, 250, 320, 350, 400]
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
            "theme", "patient_summary_anon", "cut_context_json", "cut_trigger", "dominant_theme",
            "professional_deid_version",
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

        # O tema da IA, desidentificado, e a chave de consulta — e `theme` e a
        # mesma coisa: a bolsa de palavras frequentes ("joana trabalho...")
        # nao entra em coluna nenhuma.
        self.assertEqual(primeiro["theme_predominant"], "Conflito com [NOME] no trabalho")
        self.assertEqual(segundo["theme_predominant"], "Medo de dirigir na estrada")
        self.assertEqual([c["theme"] for c in cortes], [c["theme_predominant"] for c in cortes])
        self.assertEqual(primeiro["theme_deid_reason"], "ok")
        self.assertEqual((terceiro["theme_predominant"], terceiro["theme_deid_reason"]), ("", "sem_resumo_da_ia"))
        for corte in cortes:
            for coluna in ("theme", "theme_predominant", "cut_context_json"):
                self.assertNotIn("joana", (corte[coluna] or "").lower(), coluna)
                self.assertNotIn("marcos", (corte[coluna] or "").lower(), coluna)

        # auditoria: o gatilho e o do resumo; a zona tem nome; a era e a v5.
        self.assertEqual([c["cut_trigger"] for c in cortes], ["manual", "automatico_10min", "automatico_10min"])
        self.assertEqual(primeiro["dominant_theme"], "tristeza_vs_paz_interior")
        self.assertEqual(segundo["dominant_theme"], "medo_e_sobrecarga_vs_responsabilizacao")
        self.assertIsNone(terceiro["dominant_theme"])
        self.assertEqual([c["professional_deid_version"] for c in cortes], [VERSAO_DEID] * 3)

        # A fala do paciente continua fora, em qualquer coluna.
        for corte in cortes:
            self.assertEqual(corte["patient_summary_anon"], "")
            self.assertNotIn("briguei com a", corte["cut_context_json"].lower())

        sessao = conn.execute(
            "SELECT session_modality, session_kind, summary_theme, summary_theme_deid_reason, schema_version "
            "FROM anonymous_sessions"
        ).fetchone()
        self.assertEqual(
            sessao,
            ("remote", "primeira_sessao", "Conflito com [NOME] e medo", "ok", self.main.VERSAO_DO_ACERVO),
        )
        self.assertEqual("anonymous_datamart_v5", self.main.VERSAO_DO_ACERVO)
        conn.close()

    def test_sem_linha_do_tempo_o_corte_declara_que_nao_recortou(self):
        conn = self._gravar(self._relatorio(com_linha_do_tempo=False, com_tema_da_sessao=False))
        for corte in self._cortes(conn):
            with self.subTest(corte=corte["cut_index"]):
                self.assertEqual(corte["transcript_scope"], "sem_linha_do_tempo")
                self.assertIsNone(corte["patient_word_count"])
                self.assertIsNone(corte["professional_word_count"])
                self.assertIsNone(corte["speech_density"])
                self.assertEqual(corte["intervention_category"], "sem_recorte_temporal")
        # Sem tema da IA na sessao, a bolsa de palavras de `sessionAverage`
        # NAO entra no lugar: o campo declara a ausencia.
        self.assertEqual(
            ("", "sem_resumo_da_ia"),
            conn.execute("SELECT summary_theme, summary_theme_deid_reason FROM anonymous_sessions").fetchone(),
        )
        conn.close()


if __name__ == "__main__":
    unittest.main()
