from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_access import AccessContext, decide, should_block  # noqa: E402


def context(*roles, organization_id="org-a", status="active"):
    return AccessContext.create(
        organization_id=organization_id,
        membership_id="membership-a",
        user_id="user-a",
        roles=roles,
        status=status,
    )


class TenantAccessPolicyTests(unittest.TestCase):
    def test_owner_can_manage_members(self):
        self.assertTrue(decide(context("owner"), "members.manage").allowed)
        self.assertTrue(decide(context("owner"), "assignments.manage").allowed)

    def test_administrator_and_supervisor_manage_assignments(self):
        self.assertTrue(
            decide(context("administrator"), "assignments.manage").allowed
        )
        self.assertTrue(decide(context("supervisor"), "assignments.manage").allowed)

    def test_professional_cannot_manage_members(self):
        decision = decide(context("professional"), "members.manage")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "permission_denied")

    def test_professional_reads_only_assigned_patient(self):
        professional = context("professional")
        self.assertTrue(decide(professional, "patients.read", assigned=True).allowed)
        self.assertFalse(decide(professional, "patients.read", assigned=False).allowed)

    def test_professional_can_read_own_report(self):
        decision = decide(
            context("professional"), "reports.read", owns_resource=True
        )
        self.assertTrue(decision.allowed)

    def test_supervisor_reads_reports_but_does_not_write(self):
        supervisor = context("supervisor")
        self.assertTrue(decide(supervisor, "reports.read").allowed)
        self.assertFalse(decide(supervisor, "reports.write").allowed)

    def test_auditor_reads_audit_but_not_clinical_report(self):
        auditor = context("auditor")
        self.assertTrue(decide(auditor, "audit.read").allowed)
        self.assertFalse(decide(auditor, "reports.read").allowed)

    def test_cross_organization_is_always_denied(self):
        decision = decide(
            context("owner"),
            "reports.read",
            resource_organization_id="org-b",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "cross_organization")

    def test_inactive_membership_is_denied(self):
        decision = decide(context("owner", status="revoked"), "organization.read")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "inactive_membership")

    def test_observe_never_blocks_but_enforce_does(self):
        denied = decide(context("auditor"), "reports.write")
        self.assertFalse(should_block("observe", denied))
        self.assertTrue(should_block("enforce", denied))

    def test_invalid_role_and_mode_fail_closed(self):
        with self.assertRaises(ValueError):
            context("superuser")
        with self.assertRaises(ValueError):
            should_block("invalid", decide(None, "reports.read"))


if __name__ == "__main__":
    unittest.main()
