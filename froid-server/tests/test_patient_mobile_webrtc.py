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

    def test_patient_capture_falls_back_to_independent_audio_and_video(self):
        self.assertIn("await Promise.allSettled([", self.patient_session)
        self.assertIn("audioCapture.status", self.patient_session)
        self.assertIn("videoCapture.status", self.patient_session)
        self.assertIn('mediaState === "active"', self.patient_session)

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
        self.assertEqual(self.professional_session.count("Ouvir paciente"), 2)
        self.assertIn("unlockPatientAudio", self.professional_session)

    def test_media_attachment_and_signaling_reconnects_are_bounded(self):
        self.assertIn("sameTrackSet", self.webrtc)
        self.assertIn("MAX_INITIAL_SIGNALING_RECONNECTS = 8", self.webrtc)
        self.assertIn("TERMINAL_SIGNALING_CLOSE_CODES", self.webrtc)
        self.assertIn("shouldReconnectRtcSignaling", self.patient_session)
        self.assertIn("shouldReconnectRtcSignaling", self.professional_session)

    def test_new_patient_password_is_empty_and_browser_cannot_restore_it(self):
        self.assertIn("...initialPatientForm", self.patient_invite)
        self.assertEqual(self.patient_invite.count('autoComplete="new-password"'), 2)
        self.assertEqual(self.patient_invite.count('autoComplete="current-password"'), 1)
        self.assertIn("[&_input]:bg-blue-950", self.patient_invite)
        self.assertIn("[&_input]:text-white", self.patient_invite)
        self.assertIn('sessionStorage.removeItem("froid_patient_token")', self.patient_invite)
        self.assertIn("setConsent({ ...initialConsent })", self.patient_invite)


if __name__ == "__main__":
    unittest.main()
