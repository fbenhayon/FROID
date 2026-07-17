"""Pure authorization policy for FROID Phase 2.

The policy is kept independent from FastAPI and PostgreSQL so every permission
decision can be exhaustively tested before enforcement is enabled in production.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional


VALID_ROLES = frozenset(
    {"owner", "administrator", "supervisor", "professional", "auditor"}
)
VALID_MODES = frozenset({"off", "observe", "enforce"})

ROLE_PERMISSIONS = {
    "owner": frozenset({
        "organization.read", "organization.manage", "members.manage",
        "patients.read_all", "patients.manage", "reports.read_all",
        "reports.write", "reports.delete", "assignments.manage",
        "credits.read", "credits.manage", "audit.read",
    }),
    "administrator": frozenset({
        "organization.read", "members.manage", "patients.read_all",
        "patients.manage", "reports.read_all", "reports.write",
        "reports.delete", "assignments.manage", "credits.read",
        "credits.manage", "audit.read",
    }),
    "supervisor": frozenset({
        "organization.read", "patients.read_all", "reports.read_all",
        "assignments.manage",
    }),
    "professional": frozenset({
        "organization.read", "patients.read_assigned", "reports.read_assigned",
        "reports.write", "credits.read",
    }),
    "auditor": frozenset({"organization.read", "audit.read"}),
}


@dataclass(frozen=True)
class AccessContext:
    organization_id: str
    membership_id: str
    user_id: str
    roles: FrozenSet[str]
    status: str = "active"

    @classmethod
    def create(
        cls,
        organization_id: str,
        membership_id: str,
        user_id: str,
        roles: Iterable[str],
        status: str = "active",
    ) -> "AccessContext":
        normalized_roles = frozenset(str(role).strip().lower() for role in roles)
        invalid = normalized_roles - VALID_ROLES
        if invalid:
            raise ValueError(f"Invalid FROID roles: {sorted(invalid)}")
        return cls(
            organization_id=str(organization_id),
            membership_id=str(membership_id),
            user_id=str(user_id),
            roles=normalized_roles,
            status=str(status).strip().lower(),
        )

    @property
    def permissions(self) -> FrozenSet[str]:
        combined = set()
        for role in self.roles:
            combined.update(ROLE_PERMISSIONS.get(role, ()))
        return frozenset(combined)


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
) -> AccessDecision:
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
        or ("patients.read_assigned" in permissions and assigned)
    ):
        return AccessDecision(True, "patient_scope")

    if permission == "reports.read" and (
        "reports.read_all" in permissions
        or (
            "reports.read_assigned" in permissions
            and (assigned or owns_resource)
        )
    ):
        return AccessDecision(True, "report_scope")

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
