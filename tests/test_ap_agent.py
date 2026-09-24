import pytest
from src.ap_agent.models import (
    TransactionPayload,
    InvoiceHeader,
    InvoiceLine,
    POData,
    POHeader,
    POLine,
    RCVData,
    RCVLine,
    MatchingType,
    DispositionType,
)
from src.ap_agent.core import APAgentEngine


def test_inv_99201_auto_approve():
    payload = TransactionPayload(
        invoice_header=InvoiceHeader(
            invoice_num="INV-99201",
            vendor_name="Apex Industrial Supplies",
            vendor_site="US_EAST_AP",
            po_number="PO-883401",
            currency="USD",
            terms="Net 30",
        ),
        invoice_lines=[
            InvoiceLine(
                line_num=1,
                item_id="SKU-44091",
                description="Industrial Ball Bearings 50mm",
                qty_invoiced=100,
                unit_price_invoiced=12.80,
                line_total_invoiced=1280.00,
            )
        ],
        oracle_po_data=POData(
            po_header=POHeader(
                po_num="PO-883401",
                status="OPEN",
                terms="Net 30",
                currency="USD",
                match_type=MatchingType.THREE_WAY,
            ),
            po_lines=[
                POLine(
                    line_num=1,
                    item_id="SKU-44091",
                    qty_ordered=100,
                    unit_price_agreed=12.50,
                    line_total_ordered=1250.00,
                )
            ],
        ),
        oracle_rcv_data=RCVData(
            receipt_num="RCV-40019",
            lines=[
                RCVLine(
                    line_num=1,
                    item_id="SKU-44091",
                    qty_received=100,
                    qty_accepted=100,
                )
            ],
        ),
    )

    engine = APAgentEngine()
    result = engine.evaluate(payload)

    assert result.disposition == DispositionType.AUTO_APPROVE
    assert len(result.holds_applied) == 0
    assert result.line_item_validation[0].price_variance_amount == 30.00
    assert result.line_item_validation[0].price_variance_percentage == 2.40


def test_inv_2026_8804_escalate_holds():
    payload = TransactionPayload(
        invoice_header=InvoiceHeader(
            invoice_num="INV-2026-8804",
            vendor_name="Precision Tools & Components Ltd.",
            vendor_site="TX_DALLAS_SUPP",
            po_number="PO-774021",
            currency="USD",
            terms="Net 60",
        ),
        invoice_lines=[
            InvoiceLine(
                line_num=1,
                item_id="SKU-9901-VALVE",
                description="High-Pressure Hydraulic Valve 2-inch",
                qty_invoiced=40,
                unit_price_invoiced=128.50,
                line_total_invoiced=5140.00,
            ),
            InvoiceLine(
                line_num=2,
                item_id="SKU-9902-SEAL",
                description="Industrial Rubber Seal Ring",
                qty_invoiced=100,
                unit_price_invoiced=4.10,
                line_total_invoiced=410.00,
            ),
        ],
        oracle_po_data=POData(
            po_header=POHeader(
                po_num="PO-774021",
                status="OPEN",
                terms="Net 30",
                currency="USD",
                match_type=MatchingType.THREE_WAY,
            ),
            po_lines=[
                POLine(
                    line_num=1,
                    item_id="SKU-9901-VALVE",
                    qty_ordered=40,
                    unit_price_agreed=125.00,
                    line_total_ordered=5000.00,
                ),
                POLine(
                    line_num=2,
                    item_id="SKU-9902-SEAL",
                    qty_ordered=100,
                    unit_price_agreed=4.00,
                    line_total_ordered=400.00,
                ),
            ],
        ),
        oracle_rcv_data=RCVData(
            receipt_num="RCV-88204",
            lines=[
                RCVLine(
                    line_num=1,
                    item_id="SKU-9901-VALVE",
                    qty_received=25,
                    qty_accepted=25,
                ),
                RCVLine(
                    line_num=2,
                    item_id="SKU-9902-SEAL",
                    qty_received=100,
                    qty_accepted=100,
                ),
            ],
        ),
    )

    engine = APAgentEngine()
    result = engine.evaluate(payload)

    assert result.disposition == DispositionType.ESCALATE_TO_AP_SPECIALIST
    assert "TERMS DISCREPANCY" in result.holds_applied
    assert "QTY REC" in result.holds_applied
    assert "PRICE" in result.holds_applied


def test_unmapped_line_rejection():
    payload = TransactionPayload(
        invoice_header=InvoiceHeader(
            invoice_num="INV-PAD-001",
            vendor_name="Test Vendor",
            vendor_site="SITE1",
            po_number="PO-100",
            currency="USD",
            terms="Net 30",
        ),
        invoice_lines=[
            InvoiceLine(
                line_num=1,
                item_id="SKU-1",
                description="Valid Item",
                qty_invoiced=10,
                unit_price_invoiced=10.00,
                line_total_invoiced=100.00,
            ),
            InvoiceLine(
                line_num=2,
                item_id="FEE-UNAPPROVED",
                description="Handling Fee",
                qty_invoiced=1,
                unit_price_invoiced=50.00,
                line_total_invoiced=50.00,
            ),
        ],
        oracle_po_data=POData(
            po_header=POHeader(
                po_num="PO-100",
                status="OPEN",
                terms="Net 30",
                currency="USD",
                match_type=MatchingType.TWO_WAY,
            ),
            po_lines=[
                POLine(
                    line_num=1,
                    item_id="SKU-1",
                    qty_ordered=10,
                    unit_price_agreed=10.00,
                    line_total_ordered=100.00,
                )
            ],
        ),
    )

    engine = APAgentEngine()
    result = engine.evaluate(payload)

    assert result.disposition == DispositionType.SYSTEM_REJECT
    assert "UNMAPPED LINE" in result.holds_applied
