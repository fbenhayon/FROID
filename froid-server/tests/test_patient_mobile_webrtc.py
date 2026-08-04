from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PatientMobileWebRtcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (ROOT / "froid-server" / "main.py").read_text(encoding="utf-8")
        cls.patient_session = (
            ROOT / "froid-dashboard" / "src" / "pages" / "PatientSessionPage.tsx"
        ).read_text(encoding="utf-8")
        cls.professional_session = (
            ROOT / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"
        ).read_text(encoding="utf-8")
        cls.patient_invite = (
            ROOT / "froid-dashboard" / "src" / "pages" / "PatientInvitePage.tsx"
        ).read_text(encoding="utf-8")
        cls.webrtc = (
            ROOT / "froid-dashboard" / "src" / "lib" / "webrtc.ts"
        ).read_text(encoding="utf-8")

    def test_server_relays_each_rtc_signal_exactly_once(self):
        relay = self.backend[
            self.backend.index("    async def relay(") :
            self.backend.index("    async def _safe_send(")
        ]
        self.assertEqual(relay.count("await self._safe_send(peer_socket, payload)"), 1)
        self.assertIn("del room[peer_role]", relay)
        self.assertIn('{"type": "peer-waiting"}', relay)

    def test_failed_signaling_sockets_are_not_kept_as_live_peers(self):
        safe_send = self.backend[
            self.backend.index("    async def _safe_send(") :
            self.backend.index("\n\nrtc_signals = RtcSignalManager()")
        ]
        self.assertIn("return True", safe_send)
        self.assertIn("return False", safe_send)

    def test_patient_capture_falls_back_to_sequential_audio_and_video(self):
        self.assertNotIn("await Promise.allSettled([", self.patient_session)
        self.assertIn("const audioCapture = await navigator.mediaDevices.getUserMedia", self.patient_session)
        self.assertIn("const videoCapture = await navigator.mediaDevices.getUserMedia", self.patient_session)
        self.assertIn('setMediaState(hasAudio && hasVideo ? "active" : "failed")', self.patient_session)
        self.assertIn("track.onended = markCaptureUnavailable", self.patient_session)
        self.assertIn("track.onmute = () =>", self.patient_session)

    def test_signaling_is_serialized_on_both_peers(self):
        self.assertIn("let signalQueue: Promise<void> = Promise.resolve()", self.patient_session)
        self.assertIn("signalQueue = signalQueue", self.patient_session)
        self.assertIn("let signalQueue: Promise<void> = Promise.resolve()", self.professional_session)
        self.assertIn("signalQueue = signalQueue", self.professional_session)
        self.assertIn('peer.signalingState !== "have-local-offer"', self.professional_session)

    def test_mobile_receive_only_connection_does_not_require_local_pc_media(self):
        self.assertIn(
            "!localConferenceStream.getTracks().length && !isPresentialMobileSession",
            self.professional_session,
        )

    def test_remote_sessions_never_use_professional_microphone_as_patient(self):
        self.assertIn("if (!isPresentialSession)", self.professional_session)
        self.assertIn('bioacoustic_pipeline: "remote-patient-required"', self.professional_session)
        self.assertIn(
            "O microfone do profissional não será usado como PC.",
            self.professional_session,
        )

    def test_remote_audio_replacement_and_playback_are_explicit(self):
        self.assertIn("patientRemoteAudioTrackIdRef", self.professional_session)
        self.assertIn("resetPatientAudioPipeline", self.professional_session)
        self.assertIn("track.onended", self.professional_session)
        # Um botão por layout do profissional (Detalhada, Índices, Simplificada).
        self.assertEqual(self.professional_session.count("Ouvir paciente"), 3)
        self.assertIn("unlockPatientAudio", self.professional_session)

    def test_muted_remote_tracks_are_not_reported_as_active(self):
        self.assertIn("&& !track.muted", self.webrtc)
        self.assertIn("scheduleMutedTrackRecovery", self.professional_session)
        self.assertIn("bindPatientAudioTrack", self.professional_session)
        self.assertIn("peer.restartIce()", self.professional_session)
        self.assertIn("reconectando...", self.professional_session)

    def test_connected_status_requires_actual_media_flow(self):
        # The per-page monitors were extracted into the shared evaluators of
        # lib/webrtc.ts, so this asserts the behaviour where it now lives: each
        # side reads real RTP counters, decides flow from them, and still warns
        # when the peer connection reports "connected" while nothing moves.
        self.assertIn("readRtcMediaFlowStats", self.professional_session)
        self.assertIn("evaluateInboundFlow", self.professional_session)
        self.assertIn("WebRTC conectado sem transportar mídia", self.professional_session)
        self.assertIn("readRtcMediaFlowStats", self.patient_session)
        self.assertIn("evaluateOutboundFlow", self.patient_session)
        self.assertIn("mídia sem saída", self.patient_session)
        self.assertIn("candidateType", self.webrtc)

    def test_media_attachment_and_signaling_reconnects_are_bounded(self):
        self.assertIn("sameTrackSet", self.webrtc)
        self.assertIn("MAX_INITIAL_SIGNALING_RECONNECTS = 8", self.webrtc)
        self.assertIn("TERMINAL_SIGNALING_CLOSE_CODES", self.webrtc)
        self.assertIn("shouldReconnectRtcSignaling", self.patient_session)
        self.assertIn("shouldReconnectRtcSignaling", self.professional_session)

    def test_mobile_patient_does_not_escalate_relay_on_expected_one_way_media(self):
        # No modo presencial com celular o profissional nunca envia mídia de
        # volta (recvonly do lado dele); sem essa ciência, o monitor de
        # entrada do paciente tratava a ausência perpétua de mídia do
        # profissional como falha, forçando relay TURN + restartIce em loop.
        self.assertIn(
            'const isPresentialMobile = sessionMode === "presential_mobile"',
            self.patient_session,
        )
        self.assertIn(
            "const inboundStalled = !isPresentialMobile",
            self.patient_session,
        )
        self.assertIn(
            'setSessionMode(data?.session_mode === "presential_mobile" ? "presential_mobile" : "remote")',
            self.patient_session,
        )

    def test_professional_phone_gets_responsive_layout_and_wake_lock(self):
        # Sessão celular-para-celular: o profissional pode abrir o próprio
        # dashboard no celular. As grades "Detalhada"/"Índices" exigem
        # largura mínima de monitor (1620px/1500px); em telas estreitas o
        # layout precisa cair sozinho para a "Simplificada" responsiva, e a
        # tela não pode bloquear sozinha no meio da captura de câmera/mic.
        self.assertIn(
            "window.innerWidth < 1024",
            self.professional_session,
        )
        self.assertIn(
            "grid-cols-1 gap-2 overflow-y-auto p-2 lg:grid-cols-[minmax(0,3fr)_minmax(360px,2fr)]",
            self.professional_session,
        )
        self.assertIn("requestScreenWakeLock", self.professional_session)
        self.assertIn("requestScreenWakeLock", self.patient_session)
        self.assertIn("export async function requestScreenWakeLock", self.webrtc)
        self.assertIn("visibilitychange", self.professional_session)
        self.assertIn("visibilitychange", self.patient_session)

    def test_reduced_patient_registration_keeps_password_and_single_consent(self):
        # Fase de testes: cadastro reduzido, mas a senha (e confirmacao) segue
        # obrigatoria no novo cadastro, alem da senha do paciente recorrente.
        self.assertIn("...initialPatientForm", self.patient_invite)
        self.assertEqual(self.patient_invite.count('autoComplete="new-password"'), 2)
        self.assertEqual(self.patient_invite.count('autoComplete="current-password"'), 1)
        self.assertIn("[&_input]:bg-blue-950", self.patient_invite)
        self.assertIn("[&_input]:text-white", self.patient_invite)
        self.assertIn('sessionStorage.removeItem("froid_patient_token")', self.patient_invite)
        # Consentimento unico via um checkbox.
        self.assertIn("setConsentAll(false)", self.patient_invite)
        self.assertIn("checked={consentAll}", self.patient_invite)


if __name__ == "__main__":
    unittest.main()
