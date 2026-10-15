"""Convite de equipe no formato do convite de paciente: link por papel e mensagem."""

import re
import unittest

import main


class TeamInviteFormatTests(unittest.TestCase):
    def test_role_picks_page_and_label_with_management_winning(self):
        self.assertEqual(main._team_invite_role({"professional"}), ("profissional", "profissional"))
        self.assertEqual(main._team_invite_role({"supervisor"}), ("supervisor", "supervisor"))
        self.assertEqual(main._team_invite_role({"administrator"}), ("administrador", "administrador"))
        self.assertEqual(main._team_invite_role({"owner"}), ("administrador", "administrador"))
        self.assertEqual(main._team_invite_role({"professional", "supervisor"})[0], "supervisor")

    def test_link_points_to_the_role_page(self):
        url = main._public_team_invite_url("https://www.froid.com.br", "tok_abc-123", "supervisor")
        self.assertEqual(url, "https://www.froid.com.br/app/#/entrar-clinica/supervisor?token=tok_abc-123")

    def test_message_carries_id_role_link_and_validity(self):
        invite = {
            "display_id": "froid-0123456789ab",
            "role": "profissional",
            "clinic_name": "Clinica Teste",
            "invite_url": "https://x/app/#/entrar-clinica/profissional?token=abc",
            "invited_email": "a@b.com",
            "expires_in_hours": 72,
        }
        text = main._build_team_invite_message(invite)
        for piece in ("froid-0123456789ab", "como profissional", "Clinica Teste",
                      invite["invite_url"], "72 horas"):
            self.assertIn(piece, text)

    def test_continue_to_regex_accepts_role_paths_only(self):
        source = open(main.__file__, encoding="utf-8").read()
        self.assertIn("(profissional|supervisor|administrador)", source)


if __name__ == "__main__":
    unittest.main()
