"""Pure authorization policy for FROID Phase 2.

The policy is kept independent from FastAPI and PostgreSQL so every permission
decision can be exhaustively tested before enforcement is enabled in production.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional


VALID_ROLES = frozenset(
    {
        "owner",
        "administrator",
        "supervisor",
        "professional",
        "auditor",
        # NR-1 corporate roles. They never carry clinical permissions: the
        # employer contracts the assessment, it does not get to read it.
        "compliance_manager",
        "occupational_health",
    }
)
VALID_MODES = frozenset({"off", "observe", "enforce"})

VALID_ORGANIZATION_TYPES = frozenset({"solo", "clinic", "enterprise", "legacy"})

# Permissions that expose identified clinical data about a single person.
# Inside an 'enterprise' organization the employer-side roles are stripped of
# these: NR-1 obliges the company to map psychosocial risk, it does not entitle
# it to read an employee's session. Only the assigned professional does.
CLINICAL_IDENTIFIED_PERMISSIONS = frozenset({
    "patients.read_all", "patients.read_assigned", "patients.manage",
    "reports.read_all", "reports.read_assigned", "reports.write",
    "reports.delete",
    # Stripped as well, otherwise the employer could simply assign an employee
    # to itself and read the record through the 'professional' scope. In an
    # enterprise organization only occupational_health binds employee to
    # professional.
    "assignments.manage",
})

# Roles that represent the employer inside an 'enterprise' organization.
EMPLOYER_SIDE_ROLES = frozenset({
    "owner", "administrator", "supervisor", "auditor",
    "compliance_manager",
})

ROLE_PERMISSIONS = {
    "owner": frozenset({
        "organization.read", "organization.manage", "members.manage",
        "patients.read_all", "patients.manage", "reports.read_all",
        "reports.write", "reports.delete", "assignments.manage",
        "credits.read", "credits.manage", "audit.read",
        "privacy.read", "privacy.manage",
    }),
    "administrator": frozenset({
        "organization.read", "members.manage", "patients.read_all",
        "patients.manage", "reports.read_all", "reports.write",
        "reports.delete", "assignments.manage", "credits.read",
        "credits.manage", "audit.read",
        "privacy.read", "privacy.manage",
    }),
    "supervisor": frozenset({
        "organization.read", "patients.read_all", "reports.read_all",
        "assignments.manage",
        "privacy.read",
    }),
    "professional": frozenset({
        "organization.read", "patients.read_assigned", "reports.read_assigned",
        "reports.write", "credits.read",
    }),
    "auditor": frozenset({"organization.read", "audit.read", "privacy.read"}),
    # Runs the NR-1 programme for the employer: campaigns, aggregated panel,
    # risk inventory and action plan. Reads no identified clinical record.
    "compliance_manager": frozenset({
        "organization.read",
        "nr1.campaigns.manage", "nr1.aggregate.read",
        "nr1.inventory.manage", "nr1.action_plan.manage",
        "audit.read",
    }),
    # SESMT / occupational physician: same aggregated view, plus the duty to
    # act on it. Clinical reading still requires the 'professional' role and an
    # active assignment.
    "occupational_health": frozenset({
        "organization.read",
        "nr1.aggregate.read", "nr1.inventory.manage",
        "nr1.action_plan.manage",
        # Binds employee to professional. Deliberately the only enterprise-side
        # role that can, and it still cannot read what the session produced.
        "assignments.manage",
    }),
}


def effective_role_permissions(role: str, organization_type: str = "clinic") -> FrozenSet[str]:
    """Permissions a role carries, narrowed by the organization it acts in."""
    granted = ROLE_PERMISSIONS.get(role, frozenset())
    normalized_type = str(organization_type or "clinic").strip().lower()
    if normalized_type == "enterprise" and role in EMPLOYER_SIDE_ROLES:
        return granted - CLINICAL_IDENTIFIED_PERMISSIONS
    return granted


@dataclass(frozen=True)
class AccessContext:
    organization_id: str
    membership_id: str
    user_id: str
    roles: FrozenSet[str]
    status: str = "active"
    organization_type: str = "clinic"

    @classmethod
    def create(
        cls,
        organization_id: str,
        membership_id: str,
        user_id: str,
        roles: Iterable[str],
        status: str = "active",
        organization_type: str = "clinic",
    ) -> "AccessContext":
        normalized_roles = frozenset(str(role).strip().lower() for role in roles)
        invalid = normalized_roles - VALID_ROLES
        if invalid:
            raise ValueError(f"Invalid FROID roles: {sorted(invalid)}")
        normalized_type = str(organization_type or "clinic").strip().lower()
        if normalized_type not in VALID_ORGANIZATION_TYPES:
            raise ValueError(f"Invalid FROID organization type: {organization_type!r}")
        return cls(
            organization_id=str(organization_id),
            membership_id=str(membership_id),
            user_id=str(user_id),
            roles=normalized_roles,
            status=str(status).strip().lower(),
            organization_type=normalized_type,
        )

    @property
    def permissions(self) -> FrozenSet[str]:
        combined = set()
        for role in self.roles:
            combined.update(effective_role_permissions(role, self.organization_type))
        return frozenset(combined)

    @property
    def is_enterprise(self) -> bool:
        return self.organization_type == "enterprise"


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str


def decide(
    context: Optional[AccessContext],
    permission: str,
    *,
    resource_organization_id: str = "",
    assigned: bool = False,
    owns_resource: bool = False,
    clinic_wide_reports: bool = False,
) -> AccessDecision:
    """Decide um acesso.

    ``clinic_wide_reports`` reflete a politica da organizacao (item de
    configuracao do gestor). Quando ligada, um profissional da clinica alcanca
    pacientes e relatorios de colegas da MESMA organizacao, para analise
    conjunta de conduta. O padrao e desligado, e a checagem de organizacao
    acima continua valendo em qualquer caso - a politica amplia o alcance
    dentro da clinica, nunca entre clinicas.
    """
    if context is None:
        return AccessDecision(False, "missing_context")
    if context.status != "active":
        return AccessDecision(False, "inactive_membership")
    if resource_organization_id and resource_organization_id != context.organization_id:
        return AccessDecision(False, "cross_organization")

    permissions = context.permissions
    if permission in permissions:
        return AccessDecision(True, "role_permission")

    if permission == "patients.read" and (
        "patients.read_all" in permissions
        or (
            "patients.read_assigned" in permissions
            and (assigned or clinic_wide_reports)
        )
    ):
        return AccessDecision(
            True,
            "clinic_wide_policy"
            if (clinic_wide_reports and not assigned)
            else "patient_scope",
        )

    if permission == "reports.read" and (
        "reports.read_all" in permissions
        or (
            "reports.read_assigned" in permissions
            and (assigned or owns_resource or clinic_wide_reports)
        )
    ):
        return AccessDecision(
            True,
            "clinic_wide_policy"
            if (clinic_wide_reports and not (assigned or owns_resource))
            else "report_scope",
        )

    if permission == "reports.update" and (
        "reports.delete" in permissions
        or ("reports.write" in permissions and owns_resource)
    ):
        return AccessDecision(True, "report_owner")

    return AccessDecision(False, "permission_denied")


def should_block(mode: str, decision: AccessDecision) -> bool:
    normalized_mode = str(mode or "off").strip().lower()
    if normalized_mode not in VALID_MODES:
        raise ValueError("Authorization mode must be off, observe or enforce")
    return normalized_mode == "enforce" and not decision.allowed
