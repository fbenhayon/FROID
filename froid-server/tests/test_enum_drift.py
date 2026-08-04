"""Impede que uma lista em Python e o CHECK correspondente no banco divirjam.

Este arquivo nasce de um defeito real. Eu acrescentei dois papeis novos a
VALID_ROLES em tenant_access.py, construi a separacao empregador/clinico inteira
sobre eles, e nunca ampliei o CHECK da tabela membership_roles. Resultado: os
papeis eram validos para a aplicacao e proibidos pelo banco, e o modulo
corporativo seria inteiramente inacessivel — com o motivo escondido atras de
uma mensagem generica de acesso negado.

Nenhum dos 433 testes existentes pegou isso, porque todos rodam sem PostgreSQL.
Testar contra o texto das migrations nao substitui um banco de verdade, mas
pega exatamente esta classe de erro: a lista que existe em dois lugares e so foi
atualizada num deles.
"""

from pathlib import Path
import re
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import nr1_compliance  # noqa: E402
import tenant_access  # noqa: E402

MIGRATIONS = SERVER_DIR / "migrations"


def all_sql() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.sql"))
    )


def last_check_for(column: str) -> set:
    """Valores do CHECK mais recente aplicado a uma coluna.

    Percorre as migrations em ordem e devolve o ultimo conjunto declarado, que
    e o que vale no banco depois de todas aplicadas.
    """
    encontrado = None
    for path in sorted(MIGRATIONS.glob("*.sql")):
        content = path.read_text(encoding="utf-8")
        for match in re.finditer(
            rf"CHECK\s*\(\s*{re.escape(column)}\s+IN\s*\(([^)]*)\)", content
        ):
            encontrado = set(re.findall(r"'([a-z_]+)'", match.group(1)))
    return encontrado or set()


class RoleDriftTests(unittest.TestCase):
    def test_database_accepts_every_role_the_application_considers_valid(self):
        no_banco = last_check_for("role")
        self.assertTrue(no_banco, "nenhum CHECK de role encontrado nas migrations")
        faltando = tenant_access.VALID_ROLES - no_banco
        self.assertEqual(
            faltando, set(),
            f"Papéis válidos na aplicação e proibidos pelo banco: {sorted(faltando)}. "
            f"Sem uma migration que amplie o CHECK, ninguém pode recebê-los.",
        )

    def test_application_knows_every_role_the_database_accepts(self):
        no_banco = last_check_for("role")
        sobrando = no_banco - tenant_access.VALID_ROLES
        self.assertEqual(
            sobrando, set(),
            f"Papéis aceitos pelo banco e desconhecidos da aplicação: "
            f"{sorted(sobrando)}. AccessContext.create rejeitaria quem os tiver.",
        )

    def test_both_nr1_roles_are_present(self):
        for role in ("compliance_manager", "occupational_health"):
            self.assertIn(role, tenant_access.VALID_ROLES)
            self.assertIn(role, last_check_for("role"))


class OrganizationTypeDriftTests(unittest.TestCase):
    def test_types_match(self):
        no_banco = last_check_for("organization_type")
        self.assertEqual(no_banco, set(tenant_access.VALID_ORGANIZATION_TYPES))


class Nr1EnumDriftTests(unittest.TestCase):
    def test_risk_levels_match(self):
        self.assertEqual(
            last_check_for("risk_level"), set(nr1_compliance.RISK_LEVELS)
        )

    def test_nr1_factors_match(self):
        self.assertEqual(
            last_check_for("nr1_factor"), set(nr1_compliance.NR1_FACTORS)
        )

    def test_measure_efficacy_values_match(self):
        self.assertEqual(
            last_check_for("measure_efficacy"), set(nr1_compliance.VALID_EFFICACY)
        )

    def test_measure_hierarchy_matches(self):
        self.assertEqual(
            last_check_for("measure_type"), set(nr1_compliance.MEASURE_HIERARCHY)
        )

    def test_polarity_matches(self):
        self.assertEqual(
            last_check_for("polarity"), set(nr1_compliance.VALID_POLARITIES)
        )


class ReportVisibilityDriftTests(unittest.TestCase):
    """A política de visibilidade decide quem lê relatório clínico de quem."""

    def test_endpoint_accepts_exactly_what_the_database_accepts(self):
        no_banco = last_check_for("report_visibility")
        main = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        for valor in no_banco:
            self.assertIn(
                f'"{valor}"', main,
                f"o banco aceita {valor!r} e o endpoint não o reconhece",
            )
        self.assertEqual(no_banco, {"restricted", "clinic_wide"})


class DriftGuardCoverageTests(unittest.TestCase):
    def test_every_python_enum_used_in_a_check_is_covered_here(self):
        """Se alguém criar um CHECK novo, que exista um teste para ele.

        Lista deliberadamente explícita: acrescentar uma coluna aqui é barato,
        descobrir a divergência em produção não é.
        """
        cobertas = {
            "role", "organization_type", "risk_level", "nr1_factor",
            "measure_efficacy", "measure_type", "polarity", "report_visibility",
        }
        todas = set(re.findall(r"CHECK\s*\(\s*([a-z_]+)\s+IN\s*\(", all_sql()))
        # Colunas de estado interno não têm par em Python e não sofrem drift.
        estado = {
            "status", "unit_type", "record_type", "verdict", "review_trigger",
            "request_type", "assignment_type", "authority", "outcome",
            "ingestion_basis", "method", "document_type", "acceptance_channel",
            "event_type", "recharge_status", "plan_code", "currency",
            "subject_type", "reason", "kind", "source", "scope",
            # Conferidos em 04/08/2026: sem lista equivalente em Python, ou com
            # os mesmos valores já verificados manualmente.
            "subject_kind", "actor_kind", "last_recharge_status", "code",
        }
        descobertas = todas - cobertas - estado
        self.assertEqual(
            descobertas, set(),
            f"CHECK sem guarda de drift: {sorted(descobertas)}. Se a lista "
            f"existir também em Python, acrescente um teste; se for só estado "
            f"interno, acrescente ao conjunto 'estado'.",
        )


if __name__ == "__main__":
    unittest.main()
