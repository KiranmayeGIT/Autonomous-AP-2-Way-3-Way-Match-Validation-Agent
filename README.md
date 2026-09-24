# Autonomous AP 2-Way & 3-Way Match Validation Agent

> **Oracle Fusion Cloud ERP Autonomous Accounts Payable Governance & Matching Engine**

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![Pydantic Version](https://img.shields.io/badge/pydantic-2.0%2B-green)
![License](https://img.shields.io/badge/license-MIT-purple)
![Build Status](https://img.shields.io/badge/tests-passing-brightgreen)

The **Autonomous AP Invoice Match & Governance Agent** evaluates supplier invoice inquiries against Purchase Orders (2-Way) and Goods Receipts (3-Way) in Oracle Fusion Cloud ERP ecosystems. It applies corporate tolerance policies, enforces zero-hallucination guardrails, handles deterministic Oracle Payables hold assignments, and outputs structured audit dossiers.

---

## 🏛️ Core Decision Framework: 4-Gate Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INCOMING INVOICE                               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       v
┌─────────────────────────────────────────────────────────────────────────────┐
│ GATE 1: Mandatory Header Compliance Check                                   │
│  - Active PO Status Check ('OPEN'/'APPROVED')                               │
│  - Payment Terms Match ('Net 30' vs 'Net 60')                               │
│  - Currency Alignment & Valid Supplier Site                                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       v
┌─────────────────────────────────────────────────────────────────────────────┐
│ GATE 2: Zero-Hallucination Line Binding & Receipt Resolution               │
│  - 1-to-1 PO Line Binding (Unmapped lines trigger SYSTEM_REJECT)            │
│  - Strict Receipt Lookup (Zero receipt assumed if rcv_data is NULL)          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       v
┌─────────────────────────────────────────────────────────────────────────────┐
│ GATE 3: Line-Level Matching & Hold Determination                             │
│  - 3-Way Quantity Check (Invoiced Qty > Received Qty -> Hold 'QTY REC')      │
│  - Price Variance Tolerance (<= 1.5% OR <= $50 -> AUTO_APPROVE)             │
│  - Price Variance Escalation (> 1.5% and <= 5% AND > $50 -> Hold 'PRICE')   │
│  - Price Variance Rejection (> 5% -> Hold 'PRICE REJECT')                   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       v
┌─────────────────────────────────────────────────────────────────────────────┐
│ GATE 4: Final Disposition & Audit Dossier Synthesis                          │
│  - AUTO_APPROVE / SYSTEM_REJECT / ESCALATE_TO_AP_SPECIALIST                  │
│  - Structured JSON Response & AP Specialist Audit Dossier                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Dispositions & Hold Code Reference

### 1. Dispositions
* **`AUTO_APPROVE`**: Invoice matches all mandatory header checks, quantities, and price tolerances ($\le 1.5\%$ variance OR $\le \$50$ dollar amount variance).
* **`SYSTEM_REJECT`**: Hard compliance failure (e.g., closed PO, currency mismatch, unmapped line items, price variance $> 5.0\%$).
* **`ESCALATE_TO_AP_SPECIALIST`**: Invoice placed on Oracle Payables holds requiring human review (e.g., partial delivery `QTY REC`, price variance $> 1.5\%$ and $> \$50$).

### 2. Standard Oracle Payables Hold Codes
| Hold Code | Description | Trigger Condition |
| :--- | :--- | :--- |
| **`QTY REC`** | Quantity Billed Exceeds Quantity Received | `Invoiced Qty > Received Qty` (3-Way) |
| **`PRICE`** | Unit Price Exceeds Corporate Tolerance | `Price Variance > 1.5% AND > $50.00` |
| **`PRICE REJECT`** | Price Variance Exceeds Max Rejection Ceiling | `Price Variance > 5.0% AND > $50.00` |
| **`TERMS DISCREPANCY`** | Payment Terms Mismatch | `Invoice Terms != PO Terms` |
| **`PO NOT OPEN`** | Purchase Order Status Invalid | `PO Status != 'OPEN'` |
| **`UNMAPPED LINE`** | Unapproved Line Item / Line Padding | Invoice line has no corresponding PO line |

---

## 📂 Repository Structure

```
Autonomous-AP-2-Way-3-Way-Match-Validation-Agent/
├── src/
│   └── ap_agent/
│       ├── __init__.py
│       ├── core.py           # 4-Gate Decision Engine & Governance Rules
│       ├── models.py         # Pydantic Schemas & Data Structures
│       └── cli.py            # Command Line Execution Interface
├── tests/
│   ├── run_tests.py          # Standard Library Test Runner
│   └── test_ap_agent.py      # Comprehensive Test Suite
├── examples/
│   ├── invoice_99201.json    # Auto-Approve Example Payload
│   └── invoice_2026_8804.json# Multi-Hold Escalation Example Payload
├── requirements.txt          # Python Dependencies
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and install dependencies:
```bash
git clone https://github.com/KiranmayeGIT/Autonomous-AP-2-Way-3-Way-Match-Validation-Agent.git
cd Autonomous-AP-2-Way-3-Way-Match-Validation-Agent
pip install -r requirements.txt
```

### 2. Evaluating an Invoice Payload

Run the CLI runner against an invoice JSON payload:

```bash
python3 -m src.ap_agent.cli --file examples/invoice_99201.json
```

Output:
```json
{
  "invoice_number": "INV-99201",
  "po_number": "PO-883401",
  "supplier_id": "Apex Industrial Supplies",
  "supplier_site_code": "US_EAST_AP",
  "matching_type": "3-WAY",
  "mandatory_checks": {
    "po_status_active": true,
    "supplier_site_valid": true,
    "tax_id_valid": true,
    "payment_terms_matched": true,
    "currency_matched": true
  },
  "line_item_validation": [
    {
      "line_number": 1,
      "item_number": "SKU-44091",
      "invoiced_unit_price": 12.8,
      "po_unit_price": 12.5,
      "price_variance_percentage": 2.4,
      "price_variance_amount": 30.0,
      "invoiced_quantity": 100.0,
      "po_quantity": 100.0,
      "received_quantity": 100.0,
      "line_disposition": "MATCHED"
    }
  ],
  "disposition": "AUTO_APPROVE",
  "holds_applied": [],
  "reason_code": "AUTO_APPROVED_WITHIN_TOLERANCE",
  "supplier_feedback_comments": "Invoice INV-99201 successfully matched and approved for payment under PO PO-883401.",
  "audit_dossier": {
    "summary": "Invoice INV-99201 passed all mandatory checks and tolerance policies.",
    "recommended_action": "Schedule invoice for standard payment processing under Net 30 terms.",
    "flagged_discrepancies": []
  }
}
```

### 3. Evaluating an Escalated Payload (`INV-2026-8804`)

```bash
python3 -m src.ap_agent.cli --file examples/invoice_2026_8804.json
```

Result includes active hold codes: `["TERMS DISCREPANCY", "QTY REC", "PRICE"]` and routes to `ESCALATE_TO_AP_SPECIALIST`.

---

## 🧪 Running Unit Tests

To run the automated test suite:

```bash
python3 tests/run_tests.py
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
