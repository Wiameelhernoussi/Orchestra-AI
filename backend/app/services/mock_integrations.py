from __future__ import annotations

import hashlib
import re
from typing import Any


class MockPaypalClient:
    def create_invoice(
        self,
        payload: dict[str, Any],
        request_id: str,
    ) -> dict[str, Any]:
        invoice_number = payload["detail"]["invoice_number"]
        suffix = hashlib.sha256(invoice_number.encode("utf-8")).hexdigest()[:12]
        return {"id": f"MOCK-{suffix}"}

    def send_invoice(
        self,
        invoice_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        return {"id": invoice_id, "status": "SENT", "links": []}

    def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"MOCK-[A-Fa-f0-9]{12}", invoice_id):
            raise ValueError("Unknown mock invoice.")
        return {"id": invoice_id, "status": "SENT"}

    def simulate_payment(self, invoice_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"MOCK-[A-Fa-f0-9]{12}", invoice_id):
            raise ValueError("Unknown mock invoice.")
        return {"id": invoice_id, "status": "PAID"}

    def search_invoices(self, invoice_number: str) -> dict[str, Any]:
        return {"items": []}

    def verify_webhook(self, headers: dict[str, str], event: dict[str, Any]) -> bool:
        return False

    def close(self) -> None:
        return None
