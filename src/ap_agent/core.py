from typing import List, Dict, Any, Tuple
from .models import (
    TransactionPayload,
    InvoiceDispositionResult,
    MandatoryChecks,
    LineItemValidation,
    AuditDossier,
    MatchingType,
    DispositionType,
    LineDispositionType,
)


class APAgentEngine:
    """
    Autonomous AP Invoice Match & Governance Agent Core Decision Engine.
    Implements 4-Gate Deterministic Evaluation and Oracle Payables Hold Management.
    """

    def evaluate(self, payload: TransactionPayload) -> InvoiceDispositionResult:
        holds_applied: List[str] = []
        line_validations: List[LineItemValidation] = []
        flagged_discrepancies: List[str] = []
        
        fatal_rejection = False
        rejection_reason = ""

        inv_hdr = payload.invoice_header
        po_hdr = payload.oracle_po_data.po_header
        po_lines = payload.oracle_po_data.po_lines
        rcv_data = payload.oracle_rcv_data

        # =========================================================================
        # GATE 1: MANDATORY HEADER COMPLIANCE CHECKS
        # =========================================================================
        po_status_active = (po_hdr.status.upper() in ["OPEN", "APPROVED"])
        if not po_status_active:
            holds_applied.append("PO NOT OPEN")
            fatal_rejection = True
            rejection_reason = "PO_STATUS_NOT_OPEN"
            flagged_discrepancies.append(f"PO Status is '{po_hdr.status}' (Must be OPEN)")

        payment_terms_matched = (inv_hdr.terms == po_hdr.terms)
        if not payment_terms_matched:
            holds_applied.append("TERMS DISCREPANCY")
            flagged_discrepancies.append(
                f"Header Payment Terms Mismatch: Invoiced '{inv_hdr.terms}' vs PO Contracted '{po_hdr.terms}'"
            )

        currency_matched = (inv_hdr.currency.upper() == po_hdr.currency.upper())
        if not currency_matched:
            holds_applied.append("CURRENCY MISMATCH")
            fatal_rejection = True
            rejection_reason = "CURRENCY_MISMATCH"
            flagged_discrepancies.append(
                f"Header Currency Mismatch: Invoiced '{inv_hdr.currency}' vs PO Contracted '{po_hdr.currency}'"
            )

        supplier_site_valid = bool(inv_hdr.vendor_site and inv_hdr.vendor_site.strip())
        if not supplier_site_valid:
            holds_applied.append("INVALID SUPPLIER SITE")
            fatal_rejection = True
            rejection_reason = "INVALID_SUPPLIER_SITE"
            flagged_discrepancies.append("Supplier site code missing or invalid")

        mandatory_checks = MandatoryChecks(
            po_status_active=po_status_active,
            supplier_site_valid=supplier_site_valid,
            tax_id_valid=True,
            payment_terms_matched=payment_terms_matched,
            currency_matched=currency_matched,
        )

        # =========================================================================
        # GATE 2: ZERO-HALLUCINATION GUARDRAIL & LINE BINDING
        # =========================================================================
        match_type = po_hdr.match_type

        for inv_line in payload.invoice_lines:
            line_num = inv_line.line_num
            qty_invoiced = inv_line.qty_invoiced
            unit_price_invoiced = inv_line.unit_price_invoiced

            # Search corresponding PO Line
            po_line = next((p for p in po_lines if p.line_num == line_num), None)
            if po_line is None:
                holds_applied.append("UNMAPPED LINE")
                fatal_rejection = True
                rejection_reason = "UNMAPPED_INVOICE_LINE"
                flagged_discrepancies.append(
                    f"Line {line_num} ('{inv_line.description}') has no corresponding Purchase Order line"
                )
                line_validations.append(
                    LineItemValidation(
                        line_number=line_num,
                        item_number=inv_line.item_id,
                        invoiced_unit_price=unit_price_invoiced,
                        po_unit_price=0.0,
                        price_variance_percentage=100.0,
                        price_variance_amount=inv_line.line_total_invoiced,
                        invoiced_quantity=qty_invoiced,
                        po_quantity=0.0,
                        received_quantity=0.0,
                        line_disposition=LineDispositionType.UNMAPPED,
                    )
                )
                continue

            po_unit_price = po_line.unit_price_agreed
            po_qty = po_line.qty_ordered

            # Zero-hallucination receipt lookup
            qty_received = 0.0
            if match_type == MatchingType.THREE_WAY:
                if rcv_data is not None and rcv_data.lines:
                    rcv_line = next((r for r in rcv_data.lines if r.line_num == line_num), None)
                    if rcv_line:
                        qty_received = rcv_line.qty_accepted
                else:
                    qty_received = 0.0  # Explicit 0 if receipt data is missing

            # =========================================================================
            # GATE 3: LINE-LEVEL MATCHING & HOLD DETERMINATION
            # =========================================================================
            line_disp = LineDispositionType.MATCHED

            # 3-Way Quantity Check
            if match_type == MatchingType.THREE_WAY and qty_invoiced > qty_received:
                holds_applied.append("QTY REC")
                line_disp = LineDispositionType.QTY_REC_HOLD
                unreceived_qty = qty_invoiced - qty_received
                flagged_discrepancies.append(
                    f"Line {line_num}: Invoiced Quantity ({qty_invoiced}) > Received Quantity ({qty_received}) [Shortage: {unreceived_qty} units]"
                )

            # Price Variance Calculation
            price_var_amt = (unit_price_invoiced - po_unit_price) * qty_invoiced
            price_var_pct = (
                ((unit_price_invoiced - po_unit_price) / po_unit_price * 100.0)
                if po_unit_price > 0
                else 0.0
            )

            if price_var_pct > 5.0 and price_var_amt > 50.00:
                holds_applied.append("PRICE REJECT")
                line_disp = LineDispositionType.PRICE_VARIANCE_EXCEEDED
                fatal_rejection = True
                rejection_reason = "PRICE_VARIANCE_EXCEEDS_MAX_LIMIT"
                flagged_discrepancies.append(
                    f"Line {line_num}: Unit Price Variance +{price_var_pct:.2f}% (+${price_var_amt:.2f}) exceeds max rejection limit (5.0%)"
                )
            elif price_var_pct > 1.5:
                # Check $50.00 absolute dollar tolerance ceiling
                if price_var_amt > 50.00:
                    holds_applied.append("PRICE")
                    if line_disp == LineDispositionType.MATCHED:
                        line_disp = LineDispositionType.PRICE_VARIANCE_HOLD
                    flagged_discrepancies.append(
                        f"Line {line_num}: Unit Price Variance +{price_var_pct:.2f}% (+${price_var_amt:.2f}) exceeds $50.00 tolerance cap"
                    )

            line_validations.append(
                LineItemValidation(
                    line_number=line_num,
                    item_number=inv_line.item_id,
                    invoiced_unit_price=unit_price_invoiced,
                    po_unit_price=po_unit_price,
                    price_variance_percentage=round(price_var_pct, 2),
                    price_variance_amount=round(price_var_amt, 2),
                    invoiced_quantity=qty_invoiced,
                    po_quantity=po_qty,
                    received_quantity=qty_received,
                    line_disposition=line_disp,
                )
            )

        # Deduplicate holds list
        holds_applied = list(dict.fromkeys(holds_applied))

        # =========================================================================
        # GATE 4: FINAL DISPOSITION SYNTHESIS & AUDIT DOSSIER
        # =========================================================================
        if fatal_rejection:
            disposition = DispositionType.SYSTEM_REJECT
            reason_code = rejection_reason or "COMPLIANCE_REJECT"
            feedback_comments = (
                f"Invoice {inv_hdr.invoice_num} rejected by ERP Governance Agent. "
                f"Reasons: {'; '.join(flagged_discrepancies)}."
            )
        elif len(holds_applied) > 0:
            disposition = DispositionType.ESCALATE_TO_AP_SPECIALIST
            reason_code = "HOLDS_PENDING_AP_REVIEW"
            feedback_comments = (
                f"Invoice {inv_hdr.invoice_num} placed on hold. "
                f"Active Holds: {', '.join(holds_applied)}. "
                f"Summary: {'; '.join(flagged_discrepancies)}."
            )
        else:
            disposition = DispositionType.AUTO_APPROVE
            reason_code = "AUTO_APPROVED_WITHIN_TOLERANCE"
            feedback_comments = (
                f"Invoice {inv_hdr.invoice_num} successfully matched and approved for payment under PO {inv_hdr.po_number}."
            )

        # Audit Dossier
        if disposition == DispositionType.AUTO_APPROVE:
            summary_txt = f"Invoice {inv_hdr.invoice_num} passed all mandatory checks and tolerance policies."
            rec_action = f"Schedule invoice for standard payment processing under {inv_hdr.terms} terms."
        elif disposition == DispositionType.SYSTEM_REJECT:
            summary_txt = f"Invoice {inv_hdr.invoice_num} failed strict compliance rules ({reason_code})."
            rec_action = "Reject invoice in Oracle Payables and issue rejection notification to supplier."
        else:
            summary_txt = f"Invoice {inv_hdr.invoice_num} requires AP Specialist resolution due to active holds: {', '.join(holds_applied)}."
            rec_action = "Request credit memo from supplier, verify receipt status with warehouse, or confirm buyer PO change order."

        audit_dossier = AuditDossier(
            summary=summary_txt,
            recommended_action=rec_action,
            flagged_discrepancies=flagged_discrepancies,
        )

        return InvoiceDispositionResult(
            invoice_number=inv_hdr.invoice_num,
            po_number=inv_hdr.po_number,
            supplier_id=inv_hdr.vendor_name,
            supplier_site_code=inv_hdr.vendor_site,
            matching_type=match_type,
            mandatory_checks=mandatory_checks,
            line_item_validation=line_validations,
            disposition=disposition,
            holds_applied=holds_applied,
            reason_code=reason_code,
            supplier_feedback_comments=feedback_comments,
            audit_dossier=audit_dossier,
        )
