# -*- coding: utf-8 -*-
"""Referencia populacional do Data-FROID (fase 5 do FROID Explica).

Prova contra um DuckDB em memoria com as duas tabelas do acervo: piso de
coorte sem vazar numero parcial, zero falso da v3 fora da conta, NULL fora
da conta com n_apurado ao lado, filtros de coorte, posicao de um valor, e a
lista fechada de medidas.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import duckdb
except ImportError:  # pragma: no cover - o modulo declara a ausencia
    duckdb = None

import data_froid_referencia as ref  # noqa: E402

VERSOES = ("anonymous_datamart_v4", "anonymous_datamart_v5")


def _banco(sessoes):
    """sessoes: lista de (hash, schema_version, ipm, pmin, age_bucket, cortes=[(ipm_avg, f0)])."""
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE anonymous_sessions(session_hash VARCHAR, schema_version VARCHAR, ipm_score DOUBLE, "
        "average_idm DOUBLE, average_words_per_minute DOUBLE, dissonance_count INTEGER, vocal_tension DOUBLE, "
        "average_spectral_band_index DOUBLE, session_duration INTEGER, age_bucket VARCHAR, gender VARCHAR, "
        "session_modality VARCHAR)"
    )
    conn.execute(
        "CREATE TABLE anonymous_session_cuts(session_hash VARCHAR, cut_index INTEGER, ipm_avg DOUBLE, idm_avg DOUBLE, "
        "words_per_minute DOUBLE, dissonance_count INTEGER, f0_mean DOUBLE, jitter DOUBLE, shimmer DOUBLE, zcr DOUBLE, "
        "mfcc7 DOUBLE, mfcc9 DOUBLE, spectral_band_index DOUBLE, spectral_delta_0_4 DOUBLE, spectral_theta_4_8 DOUBLE, "
        "spectral_alpha_8_12 DOUBLE, spectral_beta_12_30 DOUBLE, spectral_gamma_30_80 DOUBLE, subharmonic_5_12 DOUBLE, "
        "subharmonic_12_20 DOUBLE, subharmonic_20_40 DOUBLE, vocal_basal_85_165 DOUBLE)"
    )
    for h, versao, ipm, pmin, faixa, cortes in sessoes:
        conn.execute(
            "INSERT INTO anonymous_sessions VALUES (?, ?, ?, NULL, ?, 0, NULL, NULL, 3000, ?, 'F', 'remota')",
            [h, versao, ipm, pmin, faixa],
        )
        for i, (ipm_avg, f0) in enumerate(cortes):
            conn.execute(
                "INSERT INTO anonymous_session_cuts VALUES (?, ?, ?, NULL, NULL, 0, ?, NULL, NULL, NULL, NULL, NULL, "
                "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)",
                [h, i, ipm_avg, f0],
            )
    return conn


def _oito_sessoes_v5(ipm_base=40.0):
    return [
        (f"s{i}", "anonymous_datamart_v5", ipm_base + i, 50.0 + i, "30-39", [(ipm_base + i, 100.0 + i)])
        for i in range(8)
    ]


@unittest.skipIf(duckdb is None, "duckdb ausente: a prova contra o acervo nao roda")
class OPisoDeCoorte(unittest.TestCase):
    def test_abaixo_do_piso_nada_sai_nem_o_n_parcial(self):
        conn = _banco(_oito_sessoes_v5()[:6])
        with self.assertRaises(ref.CoorteInsuficiente) as erro:
            ref.consultar(conn, "ipm_sessao", piso=7, versoes_sem_zero_falso=VERSOES)
        self.assertNotIn("6", str(erro.exception))
        self.assertIn("menos de 7 sessoes", str(erro.exception))

    def test_no_piso_a_distribuicao_sai_com_n_e_quartis(self):
        conn = _banco(_oito_sessoes_v5())
        r = ref.consultar(conn, "ipm_sessao", piso=7, versoes_sem_zero_falso=VERSOES)
        self.assertEqual((r["sessoes"], r["n_apurado"]), (8, 8))
        self.assertAlmostEqual(r["media"], 43.5)
        self.assertAlmostEqual(r["mediana"], 43.5)
        self.assertEqual(r["versoes"], VERSOES)
        texto = ref.formatar(r)
        self.assertIn("sessoes distintas: 8 (piso de coorte 7)", texto)
        self.assertIn("nao uma norma clinica", texto)
        self.assertIn("media 43.5", texto)

    def test_o_piso_conta_sessoes_distintas_nao_cortes(self):
        # 3 sessoes com 3 cortes cada = 9 registros, mas so 3 sessoes.
        sessoes = [(f"c{i}", "anonymous_datamart_v5", 40.0, 50.0, "30-39", [(40.0, 100.0)] * 3) for i in range(3)]
        conn = _banco(sessoes)
        with self.assertRaises(ref.CoorteInsuficiente):
            ref.consultar(conn, "ipm_corte", piso=7, versoes_sem_zero_falso=VERSOES)


@unittest.skipIf(duckdb is None, "duckdb ausente: a prova contra o acervo nao roda")
class OZeroFalsoEANulo(unittest.TestCase):
    def test_a_v3_fica_fora_da_medida_acustica(self):
        # 8 sessoes v5 com IPM 40..47 e 8 sessoes v3 com 0.0 (ausencia gravada como zero).
        sessoes = _oito_sessoes_v5() + [
            (f"v3-{i}", "anonymous_datamart_v3", 0.0, 50.0, "30-39", [(0.0, 0.0)]) for i in range(8)
        ]
        conn = _banco(sessoes)
        r = ref.consultar(conn, "ipm_sessao", piso=7, versoes_sem_zero_falso=VERSOES)
        self.assertEqual(r["sessoes"], 8)
        self.assertAlmostEqual(r["media"], 43.5)  # os zeros da v3 nao puxaram a media
        self.assertIn("gravavam zero por ausencia e ficaram fora", ref.formatar(r))

    def test_medida_nao_acustica_entra_em_toda_versao(self):
        sessoes = _oito_sessoes_v5() + [
            (f"v3-{i}", "anonymous_datamart_v3", 0.0, 70.0, "30-39", []) for i in range(8)
        ]
        conn = _banco(sessoes)
        r = ref.consultar(conn, "palavras_por_minuto_sessao", piso=7, versoes_sem_zero_falso=VERSOES)
        self.assertEqual(r["sessoes"], 16)
        self.assertEqual(r["versoes"], ())
        self.assertNotIn("versoes do acervo", ref.formatar(r))

    def test_nulo_fica_fora_e_o_n_apurado_diz_quanto_entrou(self):
        sessoes = _oito_sessoes_v5()
        sessoes.append(("nulo", "anonymous_datamart_v5", None, 50.0, "30-39", []))
        conn = _banco(sessoes)
        r = ref.consultar(conn, "ipm_sessao", piso=7, versoes_sem_zero_falso=VERSOES)
        self.assertEqual((r["sessoes"], r["n_apurado"]), (8, 8))


@unittest.skipIf(duckdb is None, "duckdb ausente: a prova contra o acervo nao roda")
class FiltrosEPosicao(unittest.TestCase):
    def test_filtro_de_coorte_restringe_e_e_declarado(self):
        sessoes = _oito_sessoes_v5() + [
            (f"j{i}", "anonymous_datamart_v5", 80.0, 50.0, "20-29", [(80.0, 100.0)]) for i in range(8)
        ]
        conn = _banco(sessoes)
        r = ref.consultar(conn, "ipm_sessao", piso=7, versoes_sem_zero_falso=VERSOES, filtros={"age_bucket": "20-29"})
        self.assertEqual(r["sessoes"], 8)
        self.assertAlmostEqual(r["media"], 80.0)
        self.assertIn("filtros: age_bucket=20-29", ref.formatar(r))
        # Filtro fora da lista e ignorado, nunca interpolado.
        r2 = ref.consultar(conn, "ipm_sessao", piso=7, versoes_sem_zero_falso=VERSOES,
                           filtros={"session_hash": "s1' OR 1=1 --"})
        self.assertEqual(r2["sessoes"], 16)
        self.assertEqual(r2["filtros"], {})

    def test_a_posicao_do_valor_e_calculada_pelo_servidor(self):
        conn = _banco(_oito_sessoes_v5())  # IPM 40..47
        r = ref.consultar(conn, "ipm_sessao", piso=7, versoes_sem_zero_falso=VERSOES, valor=44.0)
        self.assertAlmostEqual(r["posicao_do_valor"], 0.5)  # 40,41,42,43 abaixo de 44
        self.assertIn("fica acima de 50% dos registros", ref.formatar(r))
        sem_valor = ref.consultar(conn, "ipm_sessao", piso=7, versoes_sem_zero_falso=VERSOES)
        self.assertIsNone(sem_valor["posicao_do_valor"])
        self.assertNotIn("fica acima", ref.formatar(sem_valor))

    def test_por_corte_le_a_tabela_de_cortes(self):
        conn = _banco(_oito_sessoes_v5())
        r = ref.consultar(conn, "f0_corte", piso=7, versoes_sem_zero_falso=VERSOES)
        self.assertEqual(r["nivel"], "corte")
        self.assertAlmostEqual(r["media"], 103.5)


class AListaDeMedidas(unittest.TestCase):
    def test_medida_fora_da_lista_e_recusada(self):
        with self.assertRaises(ref.MedidaDesconhecida):
            ref.consultar(None, "summary_text_anon", piso=7, versoes_sem_zero_falso=VERSOES)
        with self.assertRaises(ref.MedidaDesconhecida):
            ref.consultar(None, "ipm_sessao; DROP TABLE x", piso=7, versoes_sem_zero_falso=VERSOES)

    def test_nenhuma_medida_e_coluna_de_texto_e_os_nomes_sao_unicos(self):
        vedadas = {"summary_text_anon", "cut_summary_anon", "patient_summary_anon",
                   "professional_summary_anon", "theme", "theme_predominant", "recurring_themes"}
        self.assertFalse({m.coluna for m in ref.MEDIDAS} & vedadas)
        self.assertEqual(len(ref.NOMES_DAS_MEDIDAS), len(set(ref.NOMES_DAS_MEDIDAS)))
        self.assertTrue(all(m.tabela in ("anonymous_sessions", "anonymous_session_cuts") for m in ref.MEDIDAS))

    def test_os_rotulos_sao_os_do_painel(self):
        import explica_ferramentas as f

        rotulos_do_painel = {rotulo for rotulo, _campo, _casas in f.ROTULOS_DO_SNAPSHOT}
        for medida in ref.MEDIDAS:
            if medida.nivel == "corte":
                self.assertIn(medida.rotulo, rotulos_do_painel, medida.nome)


if __name__ == "__main__":
    unittest.main()
