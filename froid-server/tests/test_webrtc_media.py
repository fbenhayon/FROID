from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class WebRtcMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (ROOT / "froid-server" / "main.py").read_text(encoding="utf-8")
        cls.webrtc_source = (
            ROOT / "froid-dashboard" / "src" / "lib" / "webrtc.ts"
        ).read_text(encoding="utf-8")
        cls.professional_source = (
            ROOT / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"
        ).read_text(encoding="utf-8")
        cls.patient_source = (
            ROOT / "froid-dashboard" / "src" / "pages" / "PatientSessionPage.tsx"
        ).read_text(encoding="utf-8")

    def test_turn_credentials_are_short_lived_and_not_cached(self):
        self.assertIn('@app.get("/api/rtc/config")', self.main_source)
        self.assertIn("FROID_TURN_CREDENTIAL_TTL_SECONDS", self.main_source)
        self.assertIn("hashlib.sha1", self.main_source)
        self.assertIn('"Cache-Control": "no-store, max-age=0"', self.main_source)
        self.assertIn('"credentialExpiresAt": expires_at', self.main_source)
        self.assertIn("credentialExpiresAt", self.webrtc_source)

    def test_remote_audio_and_video_use_separate_elements(self):
        self.assertIn("attachRemoteMedia", self.webrtc_source)
        self.assertIn("videoElement.muted = true", self.webrtc_source)
        for source in (self.professional_source, self.patient_source):
            self.assertIn("remoteAudioRef", source)
            self.assertIn("remoteVideoRef", source)
            self.assertIn("attachRemoteMedia(", source)

    def test_connection_uses_candidate_pool_and_ice_restart(self):
        self.assertIn("iceCandidatePoolSize: 4", self.webrtc_source)
        self.assertIn("bundlePolicy: \"max-bundle\"", self.webrtc_source)
        self.assertIn("activateRtcRelayFallback", self.webrtc_source)
        self.assertIn('iceTransportPolicy: "relay"', self.webrtc_source)
        self.assertIn("peer.restartIce()", self.professional_source)
        self.assertIn('type: "renegotiate-request"', self.patient_source)

    def test_media_health_uses_real_rtp_bytes_and_frames(self):
        self.assertIn("readRtcMediaFlowStats", self.webrtc_source)
        self.assertIn('report.type === "inbound-rtp"', self.webrtc_source)
        self.assertIn('report.type === "outbound-rtp"', self.webrtc_source)
        self.assertIn("framesDecoded", self.webrtc_source)
        self.assertIn("framesEncoded", self.webrtc_source)
        self.assertIn("audioBytesReceived", self.professional_source)
        self.assertIn("videoFramesDecoded", self.professional_source)
        self.assertIn("audioBytesSent", self.patient_source)
        self.assertIn("videoFramesEncoded", self.patient_source)

    def test_professional_fast_path_opens_camera_and_microphone_together(self):
        self.assertIn("const combinedStream = await navigator.mediaDevices.getUserMedia", self.professional_source)
        self.assertIn("Promise.allSettled", self.professional_source)
        self.assertLess(
            self.professional_source.index("const combinedStream = await navigator.mediaDevices.getUserMedia"),
            self.professional_source.index("Promise.allSettled", self.professional_source.index("const combinedStream")),
        )


if __name__ == "__main__":
    unittest.main()
