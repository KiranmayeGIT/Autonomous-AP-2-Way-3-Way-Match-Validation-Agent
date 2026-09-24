from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class MatchingType(str, Enum):
    TWO_WAY = "2-WAY"
    THREE_WAY = "3-WAY"


class DispositionType(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    SYSTEM_REJECT = "SYSTEM_REJECT"
    ESCALATE_TO_AP_SPECIALIST = "ESCALATE_TO_AP_SPECIALIST"


class LineDispositionType(str, Enum):
    MATCHED = "MATCHED"
    PRICE_VARIANCE_EXCEEDED = "PRICE_VARIANCE_EXCEEDED"
    PRICE_VARIANCE_HOLD = "PRICE_VARIANCE_HOLD"
    QTY_REC_HOLD = "QTY_REC_HOLD"
    COMPLIANCE_FAILED = "COMPLIANCE_FAILED"
    UNMAPPED = "UNMAPPED"


class InvoiceHeader(BaseModel):
    invoice_num: str
    vendor_name: str
    vendor_site: str
    po_number: str
    currency: str = "USD"
    terms: str


class InvoiceLine(BaseModel):
    line_num: int
    item_id: str
    description: str
    qty_invoiced: float
    unit_price_invoiced: float
    line_total_invoiced: float


class POHeader(BaseModel):
    po_num: str
    status: str
    terms: str
    currency: str = "USD"
    match_type: MatchingType = MatchingType.THREE_WAY


class POLine(BaseModel):
    line_num: int
    item_id: str
    qty_ordered: float
    unit_price_agreed: float
    line_total_ordered: float


class RCVLine(BaseModel):
    line_num: int
    item_id: str
    qty_received: float
    qty_accepted: float


class RCVData(BaseModel):
    receipt_num: str
    lines: List[RCVLine] = Field(default_factory=list)


class POData(BaseModel):
    po_header: POHeader
    po_lines: List[POLine]


class TransactionPayload(BaseModel):
    invoice_header: InvoiceHeader
    invoice_lines: List[InvoiceLine]
    oracle_po_data: POData
    oracle_rcv_data: Optional[RCVData] = None


class MandatoryChecks(BaseModel):
    po_status_active: bool
    supplier_site_valid: bool
    tax_id_valid: bool = True
    payment_terms_matched: bool
    currency_matched: bool = True


class LineItemValidation(BaseModel):
    line_number: int
    item_number: str
    invoiced_unit_price: float
    po_unit_price: float
    price_variance_percentage: float
    price_variance_amount: float
    invoiced_quantity: float
    po_quantity: float
    received_quantity: float
    line_disposition: LineDispositionType


class AuditDossier(BaseModel):
    summary: str
    recommended_action: str
    flagged_discrepancies: List[str] = Field(default_factory=list)


class InvoiceDispositionResult(BaseModel):
    invoice_number: str
    po_number: str
    supplier_id: str
    supplier_site_code: str
    matching_type: MatchingType
    mandatory_checks: MandatoryChecks
    line_item_validation: List[LineItemValidation]
    disposition: DispositionType
    holds_applied: List[str] = Field(default_factory=list)
    reason_code: str
    supplier_feedback_comments: str
    audit_dossier: AuditDossier
