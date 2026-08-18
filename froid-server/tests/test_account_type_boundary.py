"""A organizacao nunca atravessa a fronteira do 'enterprise'.

Empresa NR-1 e clinica com o MESMO CNPJ resolvem para o MESMO organization_id,
e o upsert de organizacoes faz ON CONFLICT DO UPDATE do organization_type.
Sem trava, reenviar /api/professional/profile com o account_type trocado
rebaixa a organizacao de 'enterprise' para 'clinic' — e effective_role_permissions
volta a entregar patients.read_all e reports.read_all aos papeis do lado do
empregador, que e exatamente a fronteira que o modulo NR-1 existe para
sustentar.

O painel nao oferece esse caminho, mas a rota e uma API autenticada: a barreira
nao pode ser o roteador do navegador.
"""

from pathlib import Path
import sys
import unittest

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_access import (  # noqa: E402
    CLINICAL_IDENTIFIED_PERMISSIONS,
    EMPLOYER_SIDE_ROLES,
    effective_role_permissions,
)
from tenant_store import (  # noqa: E402
    organization_id_for_profile,
    organization_type_for_account,
)


class ColisaoDeOrganizacaoTests(unittest.TestCase):
    """O motivo de a trava existir, medido e nao suposto."""

    def test_mesmo_cnpj_como_empresa_ou_clinica_e_a_mesma_organizacao(self):
        empresa = organization_id_for_profile(
            "rh@empresa.com", "nr1_company", "12.345.678/0001-90"
        )
        clinica = organization_id_for_profile(
            "outro@clinica.com", "organization", "12345678000190"
        )
        # Mesma organizacao: e por isso que um cadastro consegue reescrever o
        # tipo do outro. Se um dia deixarem de colidir, a trava vira redundante
        # e este teste avisa.
        self.assertEqual(empresa, clinica)

    def test_autonomo_tem_organizacao_propria_derivada_do_email(self):
        autonomo = organization_id_for_profile("eu@psi.com", "individual", "")
        outro = organization_id_for_profile("voce@psi.com", "individual", "")
        self.assertNotEqual(autonomo, outro)

    def test_mapa_de_tipos_e_o_que_liga_o_estreitamento(self):
        self.assertEqual(organization_type_for_account("nr1_company"), "enterprise")
        self.assertEqual(organization_type_for_account("organization"), "clinic")
        self.assertEqual(organization_type_for_account("individual"), "solo")

    def test_so_enterprise_retira_o_acesso_clinico_do_empregador(self):
        for papel in sorted(EMPLOYER_SIDE_ROLES):
            como_empresa = effective_role_permissions(papel, "enterprise")
            como_clinica = effective_role_permissions(papel, "clinic")
            self.assertFalse(
                como_empresa & CLINICAL_IDENTIFIED_PERMISSIONS,
                f"{papel} manteve permissao clinica numa organizacao enterprise",
            )
            if como_clinica & CLINICAL_IDENTIFIED_PERMISSIONS:
                # O rebaixamento devolve permissao: e a consequencia concreta
                # que a trava impede.
                self.assertTrue(como_clinica - como_empresa)


class TravaDeTransicaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        cls.store = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        cls.trava = cls.backend[
            cls.backend.index("def _assert_account_type_transition(") : cls.backend.index(
                '@app.post("/api/professional/profile")'
            )
        ]

    def test_a_rota_de_perfil_chama_a_trava_antes_de_gravar(self):
        inicio = self.backend.index('@app.post("/api/professional/profile")')
        rota = self.backend[inicio : self.backend.index('@app.get("/api/subscriptions/plans")', inicio)]
        chamada = rota.index("_assert_account_type_transition(")
        gravacao = rota.index("PROFESSIONAL_PROFILES[owner_email] = profile")
        self.assertLess(chamada, gravacao)
        # E depois da validacao do valor, para nao travar em cima de lixo.
        validacao = rota.index('detail="tipo de cadastro inválido"')
        self.assertLess(validacao, chamada)

    def test_trava_recusa_os_dois_sentidos_da_travessia(self):
        # A comparacao e sobre cruzar a fronteira, nao sobre um sentido so.
        self.assertIn(
            '(anterior == "enterprise") != (alvo == "enterprise")', self.trava
        )
        self.assertIn('(atual == "enterprise") != (alvo == "enterprise")', self.trava)
        self.assertEqual(self.trava.count("status_code=409"), 2)

    def test_trava_confere_o_perfil_local_e_a_organizacao_compartilhada(self):
        # Perfil local: vale com o Postgres desligado.
        self.assertIn("PROFESSIONAL_PROFILES.get(_normalize_email(owner_email))", self.trava)
        # Organizacao do CNPJ: pega o caso em que OUTRA pessoa criou a empresa.
        self.assertIn("TENANT_STORE.organization_type(organizacao)", self.trava)
        self.assertIn("tenant_organization_id_for_profile(", self.trava)

    def test_falha_de_leitura_fecha_o_portao(self):
        depois_do_except = self.trava[self.trava.index("    except Exception:") :]
        self.assertIn("status_code=503", depois_do_except)
        # Nunca segue adiante gravando sem ter conferido.
        self.assertNotIn("return\n", depois_do_except.split("raise HTTPException")[0])

    def test_organizacao_legada_sem_tipo_nao_bloqueia_cadastro(self):
        # 'legacy' e a organizacao de quem existe desde antes do multi-tenant.
        # Tratar isso como conflito trancaria pessoas que so querem concluir o
        # proprio cadastro.
        self.assertIn('if not atual or atual == "legacy":', self.trava)

    def test_derivacao_do_id_tem_uma_fonte_so(self):
        # A trava precisa saber QUAL organizacao seria tocada. Recalcular isso
        # por fora criaria duas verdades sobre a mesma coisa.
        corpo = self.store[
            self.store.index("def _organization_for_email(") : self.store.index(
                "def _organization_for_email("
            )
            + 2000
        ]
        self.assertIn("organization_id_for_profile(", corpo)
        self.assertIn("organization_type_for_account(", corpo)
        self.assertNotIn('stable_uuid("organization", "cnpj"', corpo)


if __name__ == "__main__":
    unittest.main()
