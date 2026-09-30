"""Phase 3: RBAC V2 for Psique organizations.

Cumulative roles per membership, explicit supervision scope, and per-command
gates enforced in SQL. Enabling V2 is a per-organization, owner-authorized,
audited migration; once enabled it never silently downgrades, and V1 role
breadth stops granting clinical or financial reach (policies branch in RLS).
SUPERADMIN is a platform exception and is not grantable here by design.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psique_billing import PHASE2C_SCHEMA, BillingError, executar_comando_v2
from tenant_access import AccessContext

PHASE3_SCHEMA = PHASE2C_SCHEMA | {"042_psique_rbac_v2", "043_psique_rbac_v2_complement"}

# Mirror of the migration 042 CHECK domain; drift is guarded by tests.
V2_ROLES = ("CLINICIAN", "SECRETARY", "FINANCE", "ORG_ADMIN",
            "CLINICAL_SUPERVISOR", "AUDITOR_COMPLIANCE")


class PsiqueRbac:
    def __init__(self, connection_factory: Callable[[], Any]):
        self._connect = connection_factory

    def _call(self, sql: str, params: tuple, context: AccessContext) -> dict[str, Any]:
        return executar_comando_v2(self._connect, sql, params,
                                   context=context, schema=PHASE3_SCHEMA)

    def enable(self, context: AccessContext) -> dict[str, Any]:
        return self._call("SELECT psique_v2_rbac_enable(%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id),
                          context)

    def grant_role(self, context: AccessContext, membership_id: str, role: str) -> dict[str, Any]:
        if role not in V2_ROLES:
            # SUPERADMIN and anything else unknown is refused before SQL.
            raise BillingError("RBAC_ROLE_UNKNOWN")
        return self._call("SELECT psique_v2_role_grant(%s,%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           membership_id, role), context)

    def revoke_role(self, context: AccessContext, membership_id: str, role: str) -> dict[str, Any]:
        if role not in V2_ROLES:
            raise BillingError("RBAC_ROLE_UNKNOWN")
        return self._call("SELECT psique_v2_role_revoke(%s,%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           membership_id, role), context)

    def set_supervision(self, context: AccessContext, *, supervisor_membership_id: str,
                        supervised_membership_id: str, active: bool) -> dict[str, Any]:
        return self._call("SELECT psique_v2_supervision_set(%s,%s,%s,%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id,
                           supervisor_membership_id, supervised_membership_id, active), context)

    def capabilities(self, context: AccessContext) -> dict[str, Any]:
        return self._call("SELECT psique_v2_capabilities(%s,%s,%s)",
                          (context.organization_id, context.membership_id, context.user_id),
                          context)
