"""Garantias do motor único. Fixtures artificiais testam regras, não acurácia clínica."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import froid_facs as facs
from froid_core import SessionState


def face(*aus):
    values = {name: 0.0 for names in facs.LEGACY_MAPPING.values() for name in names}
    for au in aus:
        for name in facs.AU_BLENDSHAPES[au]:
            values[name] = 0.6
    return values


def identity(sequence, stream="camera-a", captured=None, video=None):
    return {"stream_id": stream, "sequence": sequence,
            "stream_started_at_ms": 100 if stream == "camera-a" else 200,
            "captured_at_ms": sequence * 333 if captured is None else captured,
            "video_time_ms": sequence * 333 if video is None else video}


def family(result, name):
    return next(f for f in result["families"] if f["id"] == name)


@pytest.mark.parametrize("au", list(facs.AU_BLENDSHAPES))
def test_all_sixteen_proxies_have_explicit_measurement_or_absence(au):
    result = facs.compute_action_units(face(au))
    assert len(result) == 16
    assert result[au] == (None if au == "AU23" else 0.6)


@pytest.mark.parametrize("invalid", [None, True, False, "0.6", [], {}, -0.1, 1.1, float("nan"), float("inf"), 10 ** 500])
def test_invalid_values_never_become_measured_zero(invalid):
    result = facs.compute_action_units({"browInnerUp": invalid})
    assert result["AU1"] is None


def test_partial_lateral_input_does_not_assume_other_side_zero():
    result = facs.process_facial_frame({"mouthSmileLeft": 0.9})
    assert result["status"] == "unavailable"
    assert result["action_units"] is None
    assert result["lateral"]["AU12"] == {"left": 0.9, "right": None}
    assert not family(result, "desprezo")["variants"]


def test_unknown_coefficients_do_not_certify_facs():
    result = facs.process_facial_frame({"unknown": 0.6})
    assert result["facs_source"] == "sem_apuracao"
    assert result["action_units"] is None


def test_real_zero_and_missing_have_different_meanings():
    result = facs.compute_action_units({"browInnerUp": 0.0})
    assert result["AU1"] == 0.0
    assert result["AU2"] is None


def test_mapping_corrections_preserve_underlying_raw_and_legacy_estimates():
    values = face()
    values.update(mouthShrugLower=0.8, mouthShrugUpper=0.2,
                  mouthRollLower=0.8, mouthRollUpper=0.4)
    result = facs.process_facial_frame(values)
    assert result["action_units"]["AU17"] == 0.8
    assert result["action_units"]["AU23"] is None
    assert result["legacy_estimates"]["AU17"] == 0.5
    assert result["legacy_estimates"]["AU23"] == 0.6
    assert result["raw_blendshapes"] == values


@pytest.mark.parametrize("name,aus", [
    ("sorriso", ("AU6", "AU12")),
    ("sorriso", ("AU12",)),
    ("tristeza", ("AU1", "AU4", "AU15")),
    ("tristeza", ("AU1", "AU4", "AU15", "AU17")),
    ("tristeza", ("AU6", "AU15")),
    ("raiva", ("AU4", "AU5", "AU7", "AU24")),
    ("medo", ("AU5", "AU20")),
    ("medo", ("AU1", "AU2", "AU4", "AU5", "AU20", "AU26")),
    ("surpresa", ("AU1", "AU2", "AU5", "AU26")),
    ("nojo", ("AU9", "AU15", "AU17")),
    ("nojo", ("AU10", "AU17")),
])
def test_supported_combinations(name, aus):
    result = facs.process_facial_frame(face(*aus))
    assert len(result["families"]) == 7
    assert family(result, name)["variants"]
    assert not any(result["flags"].values())
    assert result["dissonance"]["status"] == "unavailable"


def test_surprise_is_not_automatically_fear():
    result = facs.process_facial_frame(face("AU1", "AU2", "AU5", "AU26"))
    assert family(result, "surpresa")["variants"]
    assert not family(result, "medo")["variants"]


def test_shared_patterns_remain_ambiguous():
    result = facs.process_facial_frame(face("AU1", "AU2", "AU4", "AU5", "AU20", "AU26"))
    assert result["ambiguous"]
    assert family(result, "surpresa")["variants"]
    assert family(result, "medo")["variants"]
    assert len(family(result, "medo")["variants"]) == 1


@pytest.mark.parametrize("au", ["AU12", "AU14"])
@pytest.mark.parametrize("side", ["left", "right"])
def test_unilateral_does_not_disappear_in_bilateral_average(au, side):
    values = face()
    values[facs.AU_LATERAL[au][0 if side == "left" else 1]] = 0.5
    result = facs.process_facial_frame(values)
    assert result["action_units"][au] == 0.25
    assert family(result, "desprezo")["variants"][0]["side"] == side
    assert not family(result, "sorriso")["variants"]


def test_asymmetric_but_both_sides_active_is_not_strictly_unilateral():
    values = face()
    values.update(mouthDimpleLeft=0.8, mouthDimpleRight=0.5)
    assert not family(facs.process_facial_frame(values), "desprezo")["variants"]


def test_au6_is_included_and_never_certifies_genuineness():
    result = facs.process_facial_frame(face("AU6", "AU12"))
    sorriso = family(result, "sorriso")
    assert sorriso["variants"][0]["aus"] == ["AU12", "AU6"]
    assert "autenticidade" in sorriso["description"]


def test_missing_au6_is_not_absent_au6():
    values = {"mouthSmileLeft": 0.7, "mouthSmileRight": 0.7}
    result = facs.process_facial_frame(values)
    assert family(result, "sorriso")["variants"][0]["id"] == "sorriso_AU6_nao_apurada"


def tracker():
    return facs.FacialTracker(2.5, 2)


def test_two_distinct_observations_not_two_ticks_confirm():
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    for now in [100, 100.5, 101]:
        assert not family(engine.snapshot(now), "sorriso")["confirmed"]
    engine.ingest(face("AU12"), identity(2), 101)
    assert family(engine.current, "sorriso")["confirmed"]
    assert engine.archive()[0]["observations"] == 2
    assert engine.archive()[0]["clinical_confidence"] is None


@pytest.mark.parametrize("bad", [
    identity(1), identity(2, captured=333), identity(2, video=333),
    identity(0), identity(2, captured=float("nan")),
    {"stream_id": "camera-a", "sequence": True, "captured_at_ms": 500, "video_time_ms": 500},
])
def test_duplicate_invalid_or_out_of_order_never_refreshes_measurement(bad):
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    assert not engine.ingest(face("AU12"), bad, 101)
    assert engine.updated_at == 100
    assert not engine.archive()


def test_unidentified_frames_never_confirm():
    engine = tracker()
    engine.ingest(face("AU12"), None, 100)
    engine.ingest(face("AU12"), None, 101)
    assert not family(engine.current, "sorriso")["confirmed"]
    assert not engine.archive()


def test_absence_breaks_continuity_and_preserves_historical_event():
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    engine.ingest(face("AU12"), identity(2), 100.4)
    engine.ingest({}, identity(3), 100.8, "Rosto ausente.")
    assert engine.current["reason"] == "Rosto ausente."
    assert engine.current["action_units"] is None
    assert engine.archive()[0]["ended_at_ms"] == 100400
    engine.ingest(face("AU12"), identity(4), 101)
    assert not family(engine.current, "sorriso")["confirmed"]


def test_expiry_is_visible_and_resets_temporal_history():
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    assert engine.snapshot(102.6)["status"] == "unavailable"
    assert "vencida" in engine.current["reason"]
    engine.ingest(face("AU12"), identity(2), 103)
    assert not engine.archive()


def test_capture_gap_even_with_batched_network_arrival_cannot_confirm():
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    engine.ingest(face("AU12"), identity(2, captured=4000, video=4000), 100.1)
    assert not engine.archive()


def test_retired_stream_cannot_override_new_capture():
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    engine.ingest(face("AU12"), identity(1, stream="camera-b"), 100.4)
    assert not engine.ingest(face(), identity(2), 100.8)
    assert engine.stream_id == "camera-b"
    assert not engine.archive()


def test_event_between_acoustic_ticks_is_not_lost_or_duplicated():
    state = SessionState("no-voice")
    with patch("froid_core.time.time", return_value=100):
        state.update_facial_features(face("AU12"), identity(1))
        state.update_facial_features(face("AU12"), identity(2))
        state.update_facial_features(face(), identity(3))
        first = state.process_tick()
        second = state.process_tick()
    assert first["apuracao_disponivel"] is False
    assert first["facial_events"] == second["facial_events"]
    assert len(first["facial_events"]) == 1
    assert first["facial_events"][0]["ended_at_ms"] == 100000
    assert first["facial_events"][0]["raw_blendshapes"] == face("AU12")


def test_older_capture_loading_late_cannot_retire_new_capture():
    engine = tracker()
    engine.ingest(face("AU12"), identity(1, stream="camera-b"), 100)
    assert not engine.ingest(face(), identity(1, stream="camera-a"), 100.5)
    assert engine.stream_id == "camera-b"
    assert engine.updated_at == 100


def test_giant_frame_timestamp_is_rejected_without_overflow():
    engine = tracker()
    assert not engine.ingest(face(), identity(1, captured=10 ** 500), 100)
    assert engine.updated_at is None


def test_transport_delta_does_not_duplicate_and_reconnect_resynchronizes():
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    engine.ingest(face("AU12"), identity(2), 100.3)
    events, cursor = facs.facial_event_updates(engine.archive(), {})
    assert len(events) == 1
    assert facs.facial_event_updates(engine.archive(), cursor)[0] == []
    engine.ingest(face(), identity(3), 100.6)
    ended, new_cursor = facs.facial_event_updates(engine.archive(), cursor)
    assert len(ended) == 1
    assert ended[0]["ended_at_ms"] == 100300
    assert facs.facial_event_updates(engine.archive(), new_cursor)[0] == []
    assert facs.facial_event_updates(engine.archive(), {})[0] == engine.archive()


def test_invalid_face_replaces_old_reading_not_carry_forward():
    state = SessionState("invalid-face")
    state.update_facial_features(face("AU12"))
    state.update_facial_features({"unknown": 0.7})
    result = state.process_tick()
    assert result["audio_meta"]["facs_source"] == "sem_apuracao"
    assert result["audio_meta"]["facial_action_units"] is None
    assert result["facial_analysis"]["reason"]


def test_same_vocal_input_is_not_amplified_by_facial_pattern():
    from test_facs_engine import injetar_voz_real
    with patch("froid_core.time.time", return_value=100):
        plain, facial = SessionState("plain"), SessionState("facial")
        for state in (plain, facial):
            injetar_voz_real(state)
        facial.update_facial_features(face("AU12", "AU24"))
        left, right = plain.process_tick(), facial.process_tick()
    assert left["idm_score"] == right["idm_score"]
    assert left["ipm_score"] == right["ipm_score"]
    assert left["perception_zones"] == right["perception_zones"]


MAIN_TREE = ast.parse((Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8"))


def extract(name, namespace):
    node = next(n for n in MAIN_TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node = ast.parse(ast.unparse(node)).body[0]
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<main-function>", "exec"), namespace)
    return namespace[name]


class HTTPError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


@pytest.mark.parametrize("professional,owner,invite,status,session,allowed", [
    (None, "owner", "", "", "", False),
    ({"email": "other"}, "owner", "", "", "", False),
    ({"email": "OWNER"}, "owner", "", "", "", True),
    (None, "owner", "link", "accepted", "s", True),
    (None, "owner", "link", "pending", "s", False),
    (None, "owner", "link", "accepted", "other-session", False),
])
def test_facial_endpoint_keeps_invite_and_owner_authorization(professional, owner, invite, status, session, allowed):
    state = SessionState("s")
    namespace = {
        "Request": object, "HTTPException": HTTPError,
        "SESSION_INVITES": {"link": {"status": status, "session_id": session}},
        "SESSION_OWNERS": {"s": owner},
        "_current_user_from_request": lambda request: professional,
        "_normalize_email": lambda email: str(email).lower(),
        "_rate_limit_guard": lambda *args: None,
        "_client_ip": lambda request: "local-test",
        "manager": SimpleNamespace(state_for=lambda session_id: state),
    }
    endpoint = extract("submit_facial_aus", namespace)
    class Request:
        query_params = {}
        async def json(self):
            return {"invite": invite, "blendshapes": face("AU12"), "frame": identity(1)}
    if allowed:
        result = asyncio.run(endpoint("s", Request()))
        assert result["status"] == "accepted"
        assert result["facs_source"] == "real_facs"
        assert result["active_zones"] == []
    else:
        with pytest.raises(HTTPError) as caught:
            asyncio.run(endpoint("s", Request()))
        assert caught.value.status_code == 401
        assert state.latest_facial_aus is None


def test_patient_release_only_exposes_canonical_patient_fields_when_selected():
    namespace = {
        "_enrich_report_patient": lambda report: report,
        "_normalize_patient_report_items": lambda items: [i for i in items if i == "dissonances"],
        "PATIENT_REPORT_ITEM_KEYS": ["dissonances"],
        "PATIENT_REPORT_ALWAYS": ["id"],
        "_patient_identity_from_report": lambda report: {},
    }
    sanitize = extract("_sanitize_report_for_patient", namespace)
    report = {"id": "r", "facialEvents": [{
        "id": "event", "schema_version": facs.FACIAL_SCHEMA, "source": "real_facs",
        "confirmed": True, "started_at_ms": 100,
        "report": "TEXTO PROFISSIONAL", "action_units": {"AU12": 0.6},
        "patient_description": "TEXTO INJETADO",
    }]}
    result = sanitize(report, ["dissonances"])
    event = result["facialEvents"][0]
    assert event["patient_description"] == facs.PATIENT_FACIAL_DESCRIPTION
    assert "report" not in event and "action_units" not in event
    assert "facialEvents" not in sanitize(report, [])
    assert report["facialEvents"][0]["report"] == "TEXTO PROFISSIONAL"


@pytest.mark.parametrize("first_send_succeeds", [True, False])
def test_stream_face_survives_pending_voice_and_retries_unsent_event(first_send_succeeds):
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    engine.ingest(face("AU12"), identity(2), 100.3)
    sent, errors = [], []

    class Manager:
        active_sessions = {"s": {"state": SimpleNamespace(process_tick=lambda: {
            "session_id": "s", "timestamp_ms": 100300, "apuracao_disponivel": False,
            "audio_meta": {"diagnostico_acustico": {"estado": "analisando", "motivo": "analise_pendente"}},
            "facial_analysis": engine.snapshot(100.3), "facial_events": engine.archive(),
        })}}
        ticks = 0

        def is_current(self, session, connection):
            self.ticks += 1
            return self.ticks <= 2

        async def broadcast_payload(self, session, payload):
            sent.append(payload)
            return first_send_succeeds if len(sent) == 1 else True

    async def no_sleep(seconds):
        pass

    stream = extract("froid_stream_loop", {
        "manager": Manager(), "SessionState": SessionState,
        "asyncio": SimpleNamespace(sleep=no_sleep),
        "STREAM_LOGGER": SimpleNamespace(exception=lambda *args: errors.append(args)),
    })
    asyncio.run(stream("s", "connection"))
    assert not errors
    assert len(sent) == 2
    assert all(packet["facial_only"] is True for packet in sent)
    assert all(packet["perception_zones"] == [] for packet in sent)
    assert all("ipm_score" not in packet and "apuracao_disponivel" not in packet for packet in sent)
    assert len(sent[0]["facial_events"]) == 1
    assert len(sent[1]["facial_events"]) == (0 if first_send_succeeds else 1)


def test_normal_stream_preserves_vocal_payload_and_deduplicates_face():
    engine = tracker()
    engine.ingest(face("AU12"), identity(1), 100)
    engine.ingest(face("AU12"), identity(2), 100.3)
    sent, errors = [], []

    class Manager:
        active_sessions = {"s": {"state": SimpleNamespace(process_tick=lambda: {
            "session_id": "s", "timestamp_ms": 100300, "apuracao_disponivel": True,
            "ipm_score": 40, "audio_meta": {},
            "facial_analysis": engine.snapshot(100.3), "facial_events": engine.archive(),
        })}}
        ticks = 0

        def is_current(self, session, connection):
            self.ticks += 1
            return self.ticks <= 2

        async def broadcast_payload(self, session, payload):
            sent.append(payload)
            return True

    async def no_sleep(seconds):
        pass

    stream = extract("froid_stream_loop", {
        "manager": Manager(), "SessionState": SessionState,
        "asyncio": SimpleNamespace(sleep=no_sleep),
        "STREAM_LOGGER": SimpleNamespace(exception=lambda *args: errors.append(args)),
    })
    asyncio.run(stream("s", "connection"))
    assert not errors
    assert len(sent) == 2
    assert all(packet["ipm_score"] == 40 for packet in sent)
    assert all("facial_only" not in packet for packet in sent)
    assert len(sent[0]["facial_events"]) == 1
    assert sent[1]["facial_events"] == []
