"""Referência facial individual em modo de medição (decisão do dono, 08/11/2026).

Fixtures artificiais testam regras, não acurácia clínica.
"""
import froid_facs as facs


def face(level=0.0, **overrides):
    values = {name: level for names in facs.LEGACY_MAPPING.values() for name in names}
    values.update(overrides)
    return values


def identity(sequence):
    return {"stream_id": "camera-a", "sequence": sequence, "stream_started_at_ms": 100,
            "captured_at_ms": sequence * 333, "video_time_ms": sequence * 333}


def calibrate(engine, frames, start=1000.0, level=0.1, step=0.34):
    now = start
    for i in range(1, frames + 1):
        engine.ingest(face(level), identity(i), now)
        now += step
    return now, frames


def test_janela_e_a_mesma_da_voz_e_nada_e_filtrado():
    assert facs.FACE_BASELINE_WINDOW_S == 60.0
    summary = facs.FacialTracker(2.5, 2).snapshot(0.0)["facial_baseline"]
    assert summary["mode"] == "measurement_only"
    assert summary["threshold"] is None
    assert "não definido" in summary["threshold_reason"]


def test_calibra_com_mediana_do_proprio_paciente():
    engine = facs.FacialTracker(2.5, 2)
    now, seq = calibrate(engine, 100)  # 100 quadros em ~34 s, dentro da janela
    assert engine.snapshot(now)["facial_baseline"]["status"] == "calibrating"
    now = 1000.0 + 61.0
    engine.ingest(face(0.1, mouthSmileLeft=0.5, mouthSmileRight=0.5), identity(seq + 1), now)
    summary = engine.snapshot(now)["facial_baseline"]
    assert summary["status"] == "ready"
    assert summary["calibration_frames"] == 100
    assert summary["reference"]["AU12"]["median"] == 0.1
    assert summary["reference"]["AU12"]["scale"] == 0.0
    assert summary["deviation"]["AU12"]["frames"] == 1
    assert summary["deviation"]["AU12"]["max"] == 0.4


def test_calibracao_curta_se_declara_insuficiente_e_nao_mede():
    engine = facs.FacialTracker(2.5, 2)
    now, seq = calibrate(engine, facs.FACE_BASELINE_MIN_FRAMES - 1)
    engine.ingest(face(0.5), identity(seq + 1), 1000.0 + 61.0)
    summary = engine.snapshot(1061.0)["facial_baseline"]
    assert summary["status"] == "insufficient"
    assert summary["reference"] is None
    assert summary["deviation"] is None
    assert all(v is None for v in engine.current["baseline_delta"].values())


def test_au_sem_mapeamento_nao_vira_zero():
    engine = facs.FacialTracker(2.5, 2)
    now, seq = calibrate(engine, 40)
    engine.ingest(face(0.2), identity(seq + 1), 1000.0 + 61.0)
    summary = engine.snapshot(1061.0)["facial_baseline"]
    assert summary["reference"]["AU23"] is None
    assert summary["deviation"]["AU23"] is None
    assert engine.current["baseline_delta"]["AU23"] is None


def test_evento_leva_afastamento_da_referencia_sem_ser_filtrado():
    engine = facs.FacialTracker(2.5, 2)
    _, seq = calibrate(engine, 40)
    smile = face(0.1, mouthSmileLeft=0.6, mouthSmileRight=0.6)
    engine.ingest(smile, identity(seq + 1), 1061.0)
    engine.ingest(smile, identity(seq + 2), 1061.34)
    event = next(e for e in engine.archive() if e["family"] == "sorriso")
    assert event["confirmed"] is True
    assert event["baseline_status"] == "ready"
    assert event["baseline_delta"]["AU12"] == 0.5
    assert event["peak_baseline_delta"] == 0.5


def test_evento_durante_calibracao_declara_ausencia_de_referencia():
    engine = facs.FacialTracker(2.5, 2)
    smile = face(0.0, mouthSmileLeft=0.6, mouthSmileRight=0.6)
    engine.ingest(smile, identity(1), 1000.0)
    engine.ingest(smile, identity(2), 1000.34)
    event = next(e for e in engine.archive() if e["family"] == "sorriso")
    assert event["confirmed"] is True  # medição não filtra nada
    assert event["baseline_status"] == "calibrating"
    assert event["peak_baseline_delta"] is None


def test_variante_unilateral_nao_inventa_regua():
    engine = facs.FacialTracker(2.5, 2)
    _, seq = calibrate(engine, 40, level=0.0)
    lateral = face(0.0, mouthSmileLeft=0.7, mouthSmileRight=0.1)
    engine.ingest(lateral, identity(seq + 1), 1061.0)
    engine.ingest(lateral, identity(seq + 2), 1061.34)
    event = next(e for e in engine.archive() if e["family"] == "desprezo")
    assert event["peak_baseline_delta"] is None


# A nota do FROID Explica e um espelho do motor: cada numero dela tem fonte aqui.
def test_nota_do_explica_espelha_o_motor():
    import io
    import re
    from pathlib import Path
    from tools.liberar_notas_froid import LIBERADAS

    raiz = Path(__file__).resolve().parents[1]
    nome = "FROID_Leitura_Facial_Relatorio_Por_Corte.md"
    nota = io.open(raiz / "knowledge" / "approved" / "Notas_tecnicas_FROID" / nome, encoding="utf-8").read()
    assert nome in LIBERADAS
    assert f"primeiros {int(facs.FACE_BASELINE_WINDOW_S)} segundos" in nota
    assert f"pelo menos {facs.FACE_BASELINE_MIN_FRAMES} quadros" in nota
    assert facs.FacialTracker(2.5, 2).snapshot(0.0)["facial_baseline"]["threshold"] is None
    assert "ainda nao foi definido" in nota
    painel = io.open(raiz.parent / "froid-dashboard" / "src" / "lib" / "froid-face.ts", encoding="utf-8").read()
    assert re.search(r"opts\.fps \?\? 3\b", painel), "a nota diz 3 quadros por segundo"
    assert "cerca de **3 quadros por segundo**" in nota
    assert "nao detecta microexpressoes" in nota.lower()
