"""A fronteira entre o empregador e o prontuario nao depende de configuracao.

FROID_TENANT_AUTHORIZATION_MODE existe para ligar a autorizacao
multi-organizacao em etapas: em 'observe' as negacoes sao registradas e o
acesso passa. Isso e razoavel para regra de produto.

Nao e razoavel para esta: numa organizacao 'enterprise' os papeis do lado do
empregador perdem as permissoes clinicas identificadas porque a NR-1 obriga a
empresa a mapear risco psicossocial e NAO lhe da o direito de ler a sessao de um
empregado. Em producao o modo estava em 'observe', e essa negacao virava
'observed_denial' com o acesso liberado — a fronteira mais importante do produto
dependia de uma variavel de ambiente.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_access import (  # noqa: E402
    CLINICAL_IDENTIFIED_PERMISSIONS,
    EMPLOYER_SIDE_ROLES,
    VALID_MODES,
    AccessContext,
    decide,
    should_block,
)


def contexto(papel: str, tipo: str) -> AccessContext:
    return AccessContext.create(
        "org-1", "membership-1", "user-1", [papel], organization_type=tipo
    )


class FronteiraIncondicionalTests(unittest.TestCase):
    def test_bloqueia_em_todos_os_modos(self):
        for modo in sorted(VALID_MODES):
            for papel in ("owner", "administrator"):
                for permissao in sorted(CLINICAL_IDENTIFIED_PERMISSIONS):
                    decisao = decide(contexto(papel, "enterprise"), permissao)
                    if decisao.allowed:
                        continue
                    if decisao.reason != "employer_clinical_boundary":
                        continue
                    self.assertTrue(
                        should_block(modo, decisao),
                        f"modo={modo} papel={papel} permissao={permissao}",
                    )

    def test_o_motivo_distingue_a_fronteira_da_negacao_comum(self):
        """Papel que nunca teve a permissao nega por outro motivo.

        Se as duas negacoes compartilhassem o motivo, ligar o bloqueio
        incondicional passaria a bloquear regra de produto tambem — e o modo
        'observe' deixaria de servir para o que foi feito.
        """
        fronteira = decide(contexto("owner", "enterprise"), "reports.read_all")
        self.assertEqual(fronteira.reason, "employer_clinical_boundary")

        comum = decide(contexto("compliance_manager", "enterprise"), "reports.read_all")
        self.assertEqual(comum.reason, "permission_denied")
        self.assertFalse(should_block("observe", comum))

    def test_a_clinica_continua_lendo_o_proprio_prontuario(self):
        # A trava vale para organizacao 'enterprise'. Numa clinica o dono lê o
        # prontuario porque ele responde por ele.
        decisao = decide(contexto("owner", "clinic"), "reports.read_all")
        self.assertTrue(decisao.allowed)

    def test_todo_papel_do_lado_do_empregador_esta_coberto(self):
        for papel in sorted(EMPLOYER_SIDE_ROLES):
            decisao = decide(contexto(papel, "enterprise"), "patients.read_all")
            self.assertFalse(
                decisao.allowed, f"{papel} leu prontuario em organizacao enterprise"
            )


if __name__ == "__main__":
    unittest.main()
