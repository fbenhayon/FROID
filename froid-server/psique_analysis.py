"""Controlled backend pipeline adapter. Public V1 entrypoints remain unchanged.

An authenticated server caller supplies context and the authorized source;
the processor supplies its protected report and technical completion evidence.
No clinical result is fabricated here. PostgreSQL is the durable delivery store.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psique_credits import CreditError, PsiqueCredits
from tenant_access import AccessContext


@dataclass(frozen=True)
class CompletedAnalysis:
    protected_report: dict[str, Any]
    technical_complete: bool
    minimum_result_verified: bool


class AnalysisWorkflow:
    def __init__(self, credits: PsiqueCredits):
        self.credits = credits

    def run(self, context: AccessContext, source_id: str, *, execution_key: str,
            lease_until: datetime, processor: Callable[[], CompletedAnalysis]) -> dict[str, Any]:
        started = self.credits.begin(context, source_id, execution_key, lease_until)
        if not started["started"]:
            if started.get("status") == "DELIVERED":
                self.credits.reconcile(context, started["attempt_id"])
                return {**started, **self.credits.read_delivery(context, started["attempt_id"])}
            return started
        attempt_id = started["attempt_id"]
        try:
            result = processor()  # reservation is committed BEFORE billable processing
            if (result.technical_complete is not True or result.minimum_result_verified is not True
                or not result.protected_report or result.protected_report.get("transcript")):
                raise CreditError("DELIVERY_CONTRACT_NOT_MET")
            json.dumps(result.protected_report, allow_nan=False)
        except Exception:
            # Abrupt process death cannot run this handler; lease reconciliation
            # releases it later. A DB failure here remains visible, never a fake release.
            self.credits.release(context, attempt_id, "PROCESSING_FAILED_WITHOUT_DELIVERY")
            raise
        # Delivery and settlement are separate committed transactions. A lost
        # acknowledgement is reconciled from durable state; reports are never
        # deleted to roll back billing, and DELIVERED cannot be released.
        delivery = self.credits.deliver(context, attempt_id, protected_report=result.protected_report,
                                        technical_complete=True, minimum_result_verified=True)
        self.credits.read_delivery(context, attempt_id)
        settlement = self.credits.consume(context, attempt_id)
        return {**started, **delivery, "settlement": settlement, "status": "DELIVERED"}
