from pathlib import Path
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]


class RtcWaitingSessionTests(unittest.TestCase):
    def test_role_presence_tracks_connect_and_disconnect(self):
        source = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        manager_start = source.index("class RtcSignalManager:")
        manager_end = source.index("\n\nrtc_signals = RtcSignalManager()", manager_start)
        manager_source = source[manager_start:manager_end]
        self.assertIn("def role_connected(", manager_source)
        self.assertIn("self.rooms.get(session_id)", manager_source)
        self.assertIn("del room[role]", manager_source)

    def test_waiting_endpoint_is_protected_by_professional_gate(self):
        source = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        route_index = source.index('@app.get("/api/session-waiting")')
        route_block = source[route_index : route_index + 500]
        self.assertIn("_require_current_user(request)", route_block)
        self.assertIn("_require_professional_feature_access(request)", route_block)
        self.assertIn('role_connected(session_id, "patient")', source)


if __name__ == "__main__":
    unittest.main()
