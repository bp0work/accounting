# AI Finance Operations Platform

# Policy Engine Specification

## Version 1.2.0

## Filename: 10_Policy_Engine_Specification.md

## Prepared For: mmlogistix

## Date: 17 May 2026

---

# Companion Documents

| Document | Filename |
|----------|----------|
| Project Overview | 00_Project_Overview.md |
| Business Requirements | 01_Business_Requirement_Document.md |
| Technical Architecture | 02_Technical_Architecture.md |
| Cursor Development Brief | 03_Cursor_Development_Brief.md |
| Hermes Integration Specification | 04_Hermes_Integration_Spec.md |
| API Specification | 05_API_Specification.md |
| Database Schema | 06_Database_Schema_Design.md |
| AI Runtime Sequences | 07_AI_Runtime_Sequence_Diagrams.md |
| Workflow State Machine | 08_Workflow_State_Machine.md |
| Event Model | 09_Event_Model_Specification.md |
| Policy Engine | 10_Policy_Engine_Specification.md |
| Deployment Runbook | 11_Deployment_Operations_Runbook.md |
| Testing Strategy | 12_Testing_and_UAT_Strategy.md |
| Security & Compliance Specification | 13_Security_and_Compliance_Specification.md |
| Environment & Configuration Reference | 14_Environment_and_Configuration_Reference.md |
| Approval UI Specification | 15_Approval_UI_Specification.md |
| Migration and ORM Specification | 16_Migration_and_ORM_Specification.md |
| Worker Specifications | 17_Worker_Specifications.md |
| Notification Service Specification | 18_Notification_Service_Specification.md |
| Expense Worker Specification | 19_Expense_Worker_Specification.md |
| Git Workflow and Prompt Management | 20_Git_Workflow_and_Prompt_Management.md |
| OpenAPI Contract | 21_openapi.yaml |

---

# Table of Contents

1. [Policy Engine Architecture](#1-policy-engine-architecture)
2. [Policy Structure & Schema](#2-policy-structure--schema)
3. [Condition Language Specification](#3-condition-language-specification)
4. [Action Language Specification](#4-action-language-specification)
5. [Rule Evaluation Engine](#5-rule-evaluation-engine)
6. [Policy Categories](#6-policy-categories)
7. [Approval Threshold Policies](#7-approval-threshold-policies)
8. [Revenue Recognition Policies](#8-revenue-recognition-policies)
9. [Expense Recognition Policies](#9-expense-recognition-policies)
10. [FX Handling Policies](#10-fx-handling-policies)
11. [Tax Handling Policies](#11-tax-handling-policies)
12. [Reconciliation Tolerance Policies](#12-reconciliation-tolerance-policies)
13. [Policy Validation API](#13-policy-validation-api)
14. [Policy Versioning & Audit](#14-policy-versioning--audit)
15. [Default Policy Configuration (Seed Data)](#15-default-policy-configuration-seed-data)
16. [Implementation Reference (Python)](#16-implementation-reference-python)
17. [Testing Strategy](#17-testing-strategy)

---

# 1. Policy Engine Architecture

## 1.1 Design Principles

| Principle | Description |
|-----------|-------------|
| **Policy as configuration, not code** | Rules are stored in the database as structured data. Changing a threshold does not require a deployment. |
| **Explicit deny over implicit allow** | If no rule matches, the default action is to require human review. Never auto-approve by default. |
| **Deterministic evaluation** | Same inputs + same policies always produce the same result. No randomness, no external API calls during evaluation. |
| **Composable rules** | Complex policies are built from simple, reusable rule primitives. |
| **Audit every decision** | Every policy evaluation result is logged with full context for compliance. |
| **Versioned and immutable** | Published policies are immutable. Changes create new versions. Historical decisions reference the version used. |
| **Override requires authorization** | Any policy override requires documented approval at the appropriate tier. |

## 1.2 Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Case Data     │────▶│  Policy Engine  │────▶│  Evaluation     │
│   (input)       │     │                 │     │  Result         │
└─────────────────┘     │  ┌───────────┐  │     │                 │
                        │  │  Policy   │  │     │  {action,       │
┌─────────────────┐     │  │  Selector │  │     │   tier,         │
│  Active Policy  │────▶│  └───────────┘  │     │   risk_flags,   │
│  Rules (DB)     │     │       │         │     │   reason}       │
└─────────────────┘     │  ┌───────────┐  │     └─────────────────┘
                        │  │ Condition │  │              │
                        │  │ Evaluator │  │              ▼
                        │  └───────────┘  │     ┌─────────────────┐
                        │       │         │     │  Audit Log      │
                        │  ┌───────────┐  │     │  (immutable)    │
                        │  │  Action   │  │     └─────────────────┘
                        │  │  Executor │  │
                        │  └───────────┘  │
                        └─────────────────┘
```

## 1.3 Evaluation Flow

1. **Policy Selection** — Select active policies matching the case category and type
2. **Rule Ordering** — Order rules by priority (ascending, lower = higher priority)
3. **Condition Evaluation** — Evaluate each rule's conditions against case data
4. **First Match Wins** — Execute the action of the first matching rule
5. **Default Action** — If no rule matches, return the category default (typically: require approval)
6. **Audit** — Log the full evaluation context and result

## 1.4 Integration Points

| Integration | When Invoked | Uses Result For |
|-------------|-------------|-----------------|
| Workflow Orchestrator | After AI classification, before routing | Determines STP vs Assisted vs Exception |
| Approval Service | When creating approval request | Determines approval tier |
| Worker (AP/AR/Treasury) | During document processing | Validates extraction against policies |
| Journal Posting Service | Before final posting | Validates journal against accounting policies |
| API `/policies/validate` | On-demand from UI | Preview policy result without committing |

---

# 2. Policy Structure & Schema

## 2.1 Policy Entity

Stored in the `policies` table (see Database Schema Section 9):

```json
{
  "id": "uuid",
  "name": "ap_approval_thresholds",
  "display_name": "AP Approval Thresholds",
  "description": "Defines approval tiers for accounts payable invoices based on amount, counterparty risk, and document completeness",
  "category": "approval",
  "version": "1.2.0",
  "is_active": true,
  "effective_from": "2026-01-01",
  "effective_to": null,
  "rules": [ /* see Section 2.2 */ ],
  "default_action": { /* see Section 2.3 */ },
  "created_by": "uuid",
  "created_at": "2026-01-15T00:00:00Z",
  "updated_at": "2026-03-01T00:00:00Z"
}
```

## 2.2 Rule Structure

Each rule within a policy:

```json
{
  "rule_id": "uuid",
  "name": "tier_1_auto_release",
  "display_name": "Tier 1 — Auto Release",
  "description": "Low-value invoices from recurring suppliers with complete documentation",
  "priority": 10,
  "conditions": { /* see Section 3 */ },
  "action": { /* see Section 4 */ },
  "is_active": true,
  "created_at": "2026-01-15T00:00:00Z"
}
```

## 2.3 Default Action

Applied when no rule matches:

```json
{
  "default_action": {
    "type": "require_approval",
    "tier": 2,
    "reason": "No matching policy rule — defaulting to standard approval",
    "risk_flags": ["no_policy_match"]
  }
}
```

## 2.4 Policy Categories

| Category | Code | Description | Policy Count (MVP) |
|----------|------|-------------|-------------------|
| Approval thresholds | `approval` | Who must approve, based on what criteria | 3 |
| Revenue recognition | `accounting` | When and how to recognize revenue | 2 |
| Expense recognition | `accounting` | When and how to recognize expenses | 2 |
| FX handling | `accounting` | Foreign exchange transaction treatment | 2 |
| Tax handling | `tax` | GST, withholding tax, tax code assignment | 3 |
| Reconciliation tolerances | `reconciliation` | Matching tolerances and exception handling | 2 |
| Duplicate detection | `accounting` | How to detect and handle duplicates | 1 |

---

# 3. Condition Language Specification

## 3.1 Condition Structure

Conditions are stored as JSONB and evaluated by the Policy Engine.

### 3.1.1 Simple Condition

```json
{
  "field": "amount_value",
  "operator": "less_than",
  "value": "5000"
}
```

### 3.1.2 Compound Condition (AND/OR)

```json
{
  "operator": "AND",
  "conditions": [
    { "field": "amount_value", "operator": "less_than", "value": "5000" },
    { "field": "counterparty.is_recurring", "operator": "equals", "value": true },
    { "field": "risk_flags", "operator": "is_empty" }
  ]
}
```

### 3.1.3 Nested Compound

```json
{
  "operator": "OR",
  "conditions": [
    {
      "operator": "AND",
      "conditions": [
        { "field": "amount_value", "operator": "less_than", "value": "5000" },
        { "field": "confidence_score", "operator": "greater_than", "value": "0.90" }
      ]
    },
    {
      "operator": "AND",
      "conditions": [
        { "field": "counterparty.is_recurring", "operator": "equals", "value": true },
        { "field": "amount_value", "operator": "less_than", "value": "1000" }
      ]
    }
  ]
}
```

## 3.2 Field Reference

Fields are referenced using dot notation, resolved against the evaluation context.

### 3.2.1 Case Data Fields

| Field Path | Type | Example |
|-----------|------|---------|
| `case.type` | string | `"ap_invoice"` |
| `case.status` | string | `"processing"` |
| `case.priority` | string | `"high"` |
| `case.amount_value` | decimal | `15850.00` |
| `case.amount_currency` | string | `"SGD"` |
| `case.confidence_score` | decimal | `0.94` |
| `case.risk_flags` | string[] | `["amount_above_10k"]` |
| `case.tags` | string[] | `["po-matched"]` |
| `case.stp_eligible` | boolean | `true` |

### 3.2.2 Counterparty Fields

| Field Path | Type | Example |
|-----------|------|---------|
| `counterparty.id` | uuid | `"uuid"` |
| `counterparty.name` | string | `"ACME Supplies Pte Ltd"` |
| `counterparty.type` | string | `"supplier"` |
| `counterparty.is_recurring` | boolean | `true` |
| `counterparty.days_since_first_transaction` | integer | `365` |
| `counterparty.days_since_last_transaction` | integer | `30` |
| `counterparty.transaction_count_90d` | integer | `12` |

### 3.2.3 Document/Extraction Fields

| Field Path | Type | Example |
|-----------|------|---------|
| `extraction.invoice_number` | string | `"INV-44521"` |
| `extraction.invoice_date` | date | `"2026-05-01"` |
| `extraction.due_date` | date | `"2026-06-01"` |
| `extraction.line_item_count` | integer | `5` |
| `extraction.has_po_reference` | boolean | `true` |
| `extraction.has_tax_breakdown` | boolean | `true` |
| `extraction.document_completeness` | decimal | `0.95` |

### 3.2.4 AI/Classification Fields

| Field Path | Type | Example |
|-----------|------|---------|
| `ai.classification_confidence` | decimal | `0.94` |
| `ai.extraction_confidence` | decimal | `0.88` |
| `ai.model_version` | string | `"hermes-classifier-v2"` |
| `ai.inference_time_ms` | integer | `2450` |

## 3.3 Operators

### 3.3.1 Comparison Operators

| Operator | Description | Value Types | Example |
|----------|-------------|-------------|---------|
| `equals` | Exact equality | string, number, boolean | `{field: "case.type", op: "equals", value: "ap_invoice"}` |
| `not_equals` | Inequality | string, number, boolean | `{field: "case.status", op: "not_equals", value: "exception"}` |
| `greater_than` | Numeric greater than | number | `{field: "case.amount_value", op: "greater_than", value: "50000"}` |
| `greater_than_or_equal` | >= | number | `{field: "ai.confidence", op: ">=", value: "0.90"}` |
| `less_than` | Numeric less than | number | `{field: "case.amount_value", op: "less_than", value: "5000"}` |
| `less_than_or_equal` | <= | number | `{field: "case.amount_value", op: "<=", value: "5000"}` |
| `between` | Inclusive range | number (array of 2) | `{field: "case.amount_value", op: "between", value: [5000, 50000]}` |

### 3.3.2 Collection Operators

| Operator | Description | Value Types | Example |
|----------|-------------|-------------|---------|
| `contains` | Array contains value | string | `{field: "case.risk_flags", op: "contains", value: "new_supplier"}` |
| `not_contains` | Array does not contain value | string | `{field: "case.risk_flags", op: "not_contains", value: "duplicate"}` |
| `is_empty` | Array/string is empty | — | `{field: "case.risk_flags", op: "is_empty"}` |
| `is_not_empty` | Array/string is not empty | — | `{field: "extraction.invoice_number", op: "is_not_empty"}` |
| `in` | Field value in provided set | array | `{field: "case.type", op: "in", value: ["ap_invoice", "ap_po_validation"]}` |

### 3.3.3 String Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `starts_with` | String prefix match | `{field: "extraction.invoice_number", op: "starts_with", value: "INV-"}` |
| `ends_with` | String suffix match | `{field: "counterparty.name", op: "ends_with", value: "Pte Ltd"}` |
| `matches_regex` | Regex match | `{field: "extraction.invoice_number", op: "matches_regex", value: "^INV-[0-9]+$"}` |

### 3.3.4 Temporal Operators

| Operator | Description | Value Types | Example |
|----------|-------------|-------------|---------|
| `days_since` | Days since date field | integer | `{field: "extraction.invoice_date", op: "days_since", value: 90}` |
| `is_weekday` | Date is Mon-Fri | — | `{field: "extraction.invoice_date", op: "is_weekday"}` |
| `is_business_day` | Date is Singapore business day | — | `{field: "now", op: "is_business_day"}` |

### 3.3.5 Logical Operators

| Operator | Description |
|----------|-------------|
| `AND` | All nested conditions must be true |
| `OR` | At least one nested condition must be true |
| `NOT` | Negate the nested condition |

## 3.4 Field Resolution Rules

1. **Dot notation** — `counterparty.is_recurring` resolves to `context["counterparty"]["is_recurring"]`
2. **Missing fields** — If a field path does not exist in context, it resolves to `null` (not an error)
3. **Null handling** — Comparison with `null`: `equals` returns true only if both are null; numeric comparisons with null return false
4. **Type coercion** — String values in conditions are coerced to field type when unambiguous (e.g., `"5000"` → `5000` for numeric fields)

---

# 4. Action Language Specification

## 4.1 Action Structure

```json
{
  "type": "require_approval",
  "tier": 2,
  "reason": "Medium-value invoice requires finance officer approval",
  "risk_flags": ["amount_above_10k"],
  "metadata": {
    "sla_hours": 4,
    "notification_channels": ["sse", "email"]
  }
}
```

## 4.2 Action Types

| Action Type | Parameters | Description |
|-------------|-----------|-------------|
| `auto_release` | `posting_account` (optional) | STP — auto-post without human approval |
| `require_approval` | `tier` (1-3), `sla_hours` | Route to approval workflow |
| `require_document` | `document_type`, `reason` | Hold — request additional document |
| `flag_risk` | `risk_flags[]`, `action` | Add risk flags, continue processing |
| `reject` | `reason`, `category` | Reject the case permanently |
| `escalate_review` | `escalation_reason` | Send to manual review immediately |
| `apply_tax_code` | `tax_code`, `tax_rate` | Assign tax treatment |
| `assign_journal_template` | `template_id` | Use specific journal entry template |

## 4.3 Action Parameters

### auto_release

```json
{
  "type": "auto_release",
  "posting_account": "2100",
  "reason": "Low-value recurring supplier — auto-posted",
  "metadata": {
    "requires_2fa": false
  }
}
```

### require_approval

```json
{
  "type": "require_approval",
  "tier": 2,
  "reason": "Amount SGD {amount_value} exceeds auto-release threshold of SGD 5,000",
  "risk_flags": ["amount_above_threshold"],
  "sla_hours": 4,
  "notification_channels": ["sse"],
  "metadata": {
    "approver_role": "finance_officer",
    "fallback_role": "finance_manager"
  }
}
```

**Dynamic values** in `reason`: Use `{field.path}` syntax, resolved at evaluation time.

### flag_risk

```json
{
  "type": "flag_risk",
  "risk_flags": ["new_supplier_30_days", "first_time_amount"],
  "action": "continue",
  "reason": "New supplier flagged for monitoring"
}
```

The `action` parameter determines what happens after flagging:
- `"continue"` — Add flags, continue processing (other rules may still match)
- `"hold"` — Add flags, stop rule evaluation, route to pending approval

---

# 5. Rule Evaluation Engine

## 5.1 Evaluation Algorithm

```python
def evaluate_policy(case_data: dict, policy: Policy) -> EvaluationResult:
    """
    Evaluate a case against a policy's rules.
    Returns the action from the first matching rule, or the default action.
    """
    context = build_evaluation_context(case_data)
    
    # Order rules by priority (ascending — lower number = higher priority)
    sorted_rules = sorted(policy.rules, key=lambda r: r.priority)
    
    for rule in sorted_rules:
        if not rule.is_active:
            continue
        
        if evaluate_conditions(rule.conditions, context):
            return EvaluationResult(
                matched_rule=rule,
                action=rule.action,
                context=context,
                matched=True,
            )
    
    # No rule matched — return default
    return EvaluationResult(
        matched_rule=None,
        action=policy.default_action,
        context=context,
        matched=False,
    )
```

## 5.2 Evaluation Context Building

```python
def build_evaluation_context(case_data: CaseData) -> dict:
    """
    Assemble all data needed for policy evaluation.
    This is a snapshot — modifications during evaluation don't affect the source.
    """
    context = {
        "case": {
            "id": str(case_data.id),
            "type": case_data.type,
            "status": case_data.status,
            "priority": case_data.priority,
            "amount_value": float(case_data.amount_value) if case_data.amount_value else None,
            "amount_currency": case_data.amount_currency,
            "confidence_score": float(case_data.confidence_score) if case_data.confidence_score else None,
            "risk_flags": case_data.risk_flags or [],
            "tags": case_data.tags or [],
            "stp_eligible": case_data.stp_eligible,
            "created_at": case_data.created_at.isoformat() if case_data.created_at else None,
        },
        "counterparty": {},
        "extraction": {},
        "ai": {},
        "now": datetime.now(timezone.utc).isoformat(),
    }
    
    # Add counterparty if available
    if case_data.counterparty:
        cp = case_data.counterparty
        context["counterparty"] = {
            "id": str(cp.id),
            "name": cp.name,
            "type": cp.type,
            "is_recurring": cp.is_recurring,
            "days_since_first_transaction": (now - cp.first_transaction_at).days if cp.first_transaction_at else None,
            "days_since_last_transaction": (now - cp.last_transaction_at).days if cp.last_transaction_at else None,
        }
    
    # Add extraction data if available
    if case_data.extraction_data:
        context["extraction"] = case_data.extraction_data
    
    # Add AI metadata if available
    if case_data.classification_metadata:
        context["ai"] = case_data.classification_metadata
    
    return context
```

## 5.3 Evaluation Result

```python
@dataclass
class EvaluationResult:
    matched: bool
    matched_rule: Optional[PolicyRule]
    action: dict
    context: dict
    evaluation_time_ms: int = 0
    
    @property
    def requires_approval(self) -> bool:
        return self.action.get("type") == "require_approval"
    
    @property
    def approval_tier(self) -> Optional[int]:
        if self.requires_approval:
            return self.action.get("tier")
        return None
    
    @property
    def is_auto_release(self) -> bool:
        return self.action.get("type") == "auto_release"
    
    @property
    def risk_flags(self) -> list[str]:
        return self.action.get("risk_flags", [])
```

## 5.4 Multi-Policy Evaluation

When multiple policies apply (e.g., approval + tax + duplicate detection):

```python
async def evaluate_all_policies(case_data: CaseData) -> CombinedResult:
    """
    Evaluate case against all relevant active policies.
    Combine results — the most restrictive action wins.
    """
    policies = await get_active_policies_for_case_type(case_data.type)
    
    results = []
    for policy in policies:
        result = evaluate_policy(case_data, policy)
        results.append(result)
    
    # Combine: most restrictive action wins
    # Order of restrictiveness: reject > require_approval(t3) > require_approval(t2) > flag_risk > require_approval(t1) > auto_release
    combined = combine_results(results)
    
    # Audit all evaluations
    await audit_policy_evaluation(case_data.id, results, combined)
    
    return combined
```

### Restrictiveness Ranking

| Rank | Action Type | Description |
|------|-------------|-------------|
| 1 (most) | `reject` | Case rejected |
| 2 | `escalate_review` | Sent to manual review |
| 3 | `require_approval` tier 3 | CFO approval required |
| 4 | `require_approval` tier 2 | Finance officer/manager approval |
| 5 | `require_document` | Additional document required |
| 6 | `flag_risk` | Risk flags added |
| 7 | `require_approval` tier 1 | Auto-release lane (still technically approval) |
| 8 (least) | `auto_release` | Full STP |

---

# 6. Policy Categories

## 6.1 Category Overview

```
approval/
├── ap_approval_thresholds        (Section 7)
├── ar_approval_thresholds
└── journal_posting_authority

accounting/
├── revenue_recognition           (Section 8)
├── expense_recognition           (Section 9)
├── fx_handling                   (Section 10)
└── duplicate_detection

tax/
├── gst_handling                  (Section 11)
├── withholding_tax
└── tax_code_assignment

reconciliation/
├── matching_tolerances           (Section 12)
└── suspense_account_handling
```

## 6.2 Category-Case Type Mapping

| Case Type | Relevant Policy Categories |
|-----------|---------------------------|
| `ap_invoice` | approval, accounting, tax, duplicate_detection |
| `ap_po_validation` | approval, accounting |
| `ar_invoice` | approval, accounting, tax, revenue_recognition |
| `ar_payment_advice` | approval, accounting, reconciliation |
| `treasury_reconciliation` | reconciliation |
| `treasury_fx` | accounting (fx_handling), reconciliation |
| `general_inquiry` | — (no policies) |

---

# 7. Approval Threshold Policies

> **Shipped implementation (`0.14.9-binding-authority`):** Tier evaluation is **not** the full JSON rule engine below for AP/AR/expense intake. Production uses `PolicyEngine.evaluate_approval_tier()` with thresholds loaded from `policies` (`ap_approval_thresholds`, `ar_approval_thresholds`, `expense_approval_thresholds`). Client Admin edits via `GET/PATCH /api/admin/binding-authority` (`05` §4.16d.14). Defaults: Tier 1 ≤ SGD 3,000 + confidence ≥ 0.90 → STP; amount ≥ Tier 3 threshold (10,000) or blocking risk flags → Tier 3 CFO; else Tier 2 Accounts Manager. Workers: `accfin/workers/{ap,ar,expense}/handlers.py`; escalation: `workers/common/binding_authority_escalation.py`. Migration `060` (`16` §10).

## 7.1 AP Invoice Approval Thresholds

Policy: `ap_approval_thresholds`

### Rules

```json
{
  "policy": {
    "name": "ap_approval_thresholds",
    "display_name": "AP Invoice Approval Thresholds",
    "category": "approval",
    "default_action": {
      "type": "require_approval",
      "tier": 2,
      "reason": "Default: standard approval required"
    },
    "rules": [
      {
        "rule_id": "uuid-001",
        "name": "tier_1_auto_release",
        "priority": 10,
        "description": "Low-value recurring supplier invoices — full STP",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "case.amount_value", "operator": "less_than", "value": "5000" },
            { "field": "counterparty.is_recurring", "operator": "equals", "value": true },
            { "field": "case.risk_flags", "operator": "is_empty" },
            { "field": "ai.classification_confidence", "operator": "greater_than_or_equal", "value": "0.90" },
            { "field": "ai.extraction_confidence", "operator": "greater_than_or_equal", "value": "0.90" },
            { "field": "extraction.has_tax_breakdown", "operator": "equals", "value": true },
            { "field": "extraction.document_completeness", "operator": "greater_than_or_equal", "value": "0.95" }
          ]
        },
        "action": {
          "type": "auto_release",
          "reason": "Low-value recurring supplier with complete documentation — STP approved"
        }
      },
      {
        "rule_id": "uuid-002",
        "name": "tier_2_standard_approval",
        "priority": 20,
        "description": "Medium-value invoices or new suppliers",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "case.amount_value", "operator": "less_than", "value": "50000" },
            { "field": "case.risk_flags", "operator": "not_contains", "value": "high_risk" }
          ]
        },
        "action": {
          "type": "require_approval",
          "tier": 2,
          "reason": "Invoice amount SGD {case.amount_value} requires finance officer approval",
          "risk_flags": ["amount_above_5k"],
          "sla_hours": 4
        }
      },
      {
        "rule_id": "uuid-003",
        "name": "tier_3_executive_approval",
        "priority": 30,
        "description": "High-value invoices or flagged transactions",
        "conditions": {
          "operator": "OR",
          "conditions": [
            { "field": "case.amount_value", "operator": "greater_than_or_equal", "value": "50000" },
            { "field": "case.risk_flags", "operator": "contains", "value": "high_risk" },
            { "field": "case.risk_flags", "operator": "contains", "value": "policy_override_requested" }
          ]
        },
        "action": {
          "type": "require_approval",
          "tier": 3,
          "reason": "High-value or flagged invoice requires executive approval",
          "risk_flags": ["executive_approval_required"],
          "sla_hours": 8
        }
      },
      {
        "rule_id": "uuid-004",
        "name": "new_supplier_hold",
        "priority": 15,
        "description": "New supplier invoices require additional verification",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "counterparty.is_recurring", "operator": "equals", "value": false },
            { "field": "case.amount_value", "operator": "greater_than_or_equal", "value": "1000" }
          ]
        },
        "action": {
          "type": "require_approval",
          "tier": 2,
          "reason": "New supplier — first transaction requires verification",
          "risk_flags": ["new_supplier"],
          "sla_hours": 4
        }
      },
      {
        "rule_id": "uuid-005",
        "name": "incomplete_documentation",
        "priority": 5,
        "description": "Missing tax breakdown or incomplete extraction",
        "conditions": {
          "operator": "OR",
          "conditions": [
            { "field": "extraction.has_tax_breakdown", "operator": "equals", "value": false },
            { "field": "extraction.document_completeness", "operator": "less_than", "value": "0.70" }
          ]
        },
        "action": {
          "type": "require_document",
          "document_type": "tax_invoice_or_statement",
          "reason": "Incomplete documentation — tax breakdown missing or extraction confidence too low"
        }
      }
    ]
  }
}
```

## 7.2 AR Invoice Approval Thresholds

Policy: `ar_approval_thresholds`

```json
{
  "policy": {
    "name": "ar_approval_thresholds",
    "display_name": "AR Invoice Approval Thresholds",
    "category": "approval",
    "default_action": {
      "type": "auto_release",
      "reason": "AR invoices are outbound — default auto-post to receivables"
    },
    "rules": [
      {
        "rule_id": "uuid-010",
        "name": "large_ar_review",
        "priority": 10,
        "description": "Large AR invoices require review",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "case.amount_value", "operator": "greater_than_or_equal", "value": "100000" },
            { "field": "counterparty.is_recurring", "operator": "equals", "value": false }
          ]
        },
        "action": {
          "type": "require_approval",
          "tier": 2,
          "reason": "Large AR invoice from new customer requires review",
          "risk_flags": ["large_ar_new_customer"],
          "sla_hours": 4
        }
      }
    ]
  }
}
```

## 7.3 Journal Posting Authority

Policy: `journal_posting_authority`

```json
{
  "policy": {
    "name": "journal_posting_authority",
    "display_name": "Journal Posting Authority",
    "category": "approval",
    "description": "Who can approve journal entries and financial postings",
    "default_action": {
      "type": "require_approval",
      "tier": 2,
      "reason": "Journal posting requires finance approval"
    },
    "rules": [
      {
        "rule_id": "uuid-020",
        "name": "standard_journal",
        "priority": 10,
        "description": "Routine journals under threshold",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "case.amount_value", "operator": "less_than", "value": "50000" },
            { "field": "case.risk_flags", "operator": "is_empty" }
          ]
        },
        "action": {
          "type": "require_approval",
          "tier": 2,
          "reason": "Standard journal — finance officer approval",
          "metadata": {
            "approver_role": "finance_officer"
          }
        }
      },
      {
        "rule_id": "uuid-021",
        "name": "executive_journal",
        "priority": 20,
        "description": "Large or complex journals",
        "conditions": {
          "operator": "OR",
          "conditions": [
            { "field": "case.amount_value", "operator": "greater_than_or_equal", "value": "50000" },
            { "field": "case.risk_flags", "operator": "contains", "value": "complex_structure" }
          ]
        },
        "action": {
          "type": "require_approval",
          "tier": 3,
          "reason": "Large or complex journal — executive approval required",
          "metadata": {
            "approver_role": "cfo"
          }
        }
      }
    ]
  }
}
```

---

# 8. Revenue Recognition Policies

## 8.1 Revenue Recognition Timing

Policy: `revenue_recognition_timing`

```json
{
  "policy": {
    "name": "revenue_recognition_timing",
    "display_name": "Revenue Recognition Timing",
    "category": "accounting",
    "description": "When to recognize revenue based on invoice terms",
    "rules": [
      {
        "rule_id": "uuid-100",
        "name": "point_in_time",
        "priority": 10,
        "description": "Standard goods/services — recognize at invoice date",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "extraction.service_type", "operator": "in", "value": ["goods", "standard_services"] }
          ]
        },
        "action": {
          "type": "assign_journal_template",
          "template_id": "revenue_point_in_time",
          "reason": "Point-in-time revenue recognition",
          "metadata": {
            "recognition_basis": "invoice_date",
            "debit_account": "1300",
            "credit_account": "4100"
          }
        }
      },
      {
        "rule_id": "uuid-101",
        "name": "over_time",
        "priority": 20,
        "description": "Long-term services — recognize over service period",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "extraction.service_type", "operator": "equals", "value": "recurring_services" },
            { "field": "extraction.contract_duration_months", "operator": "greater_than", "value": "1" }
          ]
        },
        "action": {
          "type": "assign_journal_template",
          "template_id": "revenue_over_time",
          "reason": "Revenue recognized over contract period",
          "metadata": {
            "recognition_basis": "contract_period",
            "debit_account": "1300",
            "credit_account": "2200"
          }
        }
      }
    ]
  }
}
```

---

# 9. Expense Recognition Policies

> **Scope note:** This section covers **accounting recognition policies for supplier invoices** — i.e. when and how to record AP invoice expenses in the general ledger (accrual vs prepayment treatment). It is **not** the employee expense claim policy engine. Employee expense claim validation (per-diem limits, receipt thresholds, category controls, duplicate detection) is handled by the `expense_policies` table and the Expense Worker (`19_Expense_Worker_Specification.md` §5). The two are independent: `19` §5.2 calls the PolicyEngine with `case_type = 'expense_claim'` and the engine evaluates `expense_policies` rows — it does not evaluate `expense_recognition_rules`. The FX policy in §10 of this document is the only cross-dependency (`19` §5.2 references it for non-SGD line items).

## 9.1 Expense Recognition Rules

Policy: `expense_recognition_rules`

```json
{
  "policy": {
    "name": "expense_recognition_rules",
    "display_name": "Expense Recognition Rules",
    "category": "accounting",
    "description": "When and how to recognize expenses from supplier invoices",
    "rules": [
      {
        "rule_id": "uuid-110",
        "name": "accrual_expense",
        "priority": 10,
        "description": "Default accrual — recognize when goods/services received",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "extraction.has_po_reference", "operator": "equals", "value": true },
            { "field": "extraction.has_grn_reference", "operator": "equals", "value": true }
          ]
        },
        "action": {
          "type": "assign_journal_template",
          "template_id": "expense_accrual_matched",
          "reason": "PO and GRN matched — expense recognized on receipt",
          "metadata": {
            "debit_account": "5200",
            "credit_account": "2100",
            "recognition_basis": "goods_received"
          }
        }
      },
      {
        "rule_id": "uuid-111",
        "name": "prepayment",
        "priority": 20,
        "description": "Payment before receipt — record as prepayment",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "extraction.payment_terms", "operator": "equals", "value": "advance" }
          ]
        },
        "action": {
          "type": "assign_journal_template",
          "template_id": "expense_prepayment",
          "reason": "Advance payment — record as prepayment asset",
          "metadata": {
            "debit_account": "1500",
            "credit_account": "1200",
            "recognition_basis": "payment_date"
          }
        }
      }
    ]
  }
}
```

---

# 10. FX Handling Policies

## 10.1 Foreign Exchange Rules

Policy: `fx_transaction_handling`

```json
{
  "policy": {
    "name": "fx_transaction_handling",
    "display_name": "FX Transaction Handling",
    "category": "accounting",
    "description": "How to handle invoices and payments in foreign currency",
    "rules": [
      {
        "rule_id": "uuid-120",
        "name": "fx_invoice_conversion",
        "priority": 10,
        "description": "Convert foreign currency invoice to functional currency",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "case.amount_currency", "operator": "not_equals", "value": "SGD" }
          ]
        },
        "action": {
          "type": "assign_journal_template",
          "template_id": "fx_invoice",
          "reason": "Foreign currency invoice — convert at transaction date rate",
          "metadata": {
            "use_exchange_rate": "transaction_date",
            "fx_gain_loss_account": "5500",
            "requires_fx_approval": true
          }
        }
      },
      {
        "rule_id": "uuid-121",
        "name": "fx_large_exposure",
        "priority": 5,
        "description": "Flag large FX exposures for treasury review",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "case.amount_currency", "operator": "not_equals", "value": "SGD" },
            { "field": "case.amount_value", "operator": "greater_than_or_equal", "value": "100000" }
          ]
        },
        "action": {
          "type": "flag_risk",
          "risk_flags": ["large_fx_exposure"],
          "action": "continue",
          "reason": "Large FX exposure — flagged for treasury monitoring"
        }
      }
    ]
  }
}
```

## 10.2 FX Rate Source

| Currency Pair | Rate Source | Update Frequency |
|---------------|-------------|------------------|
| SGD/USD | MAS reference rate | Daily 09:00 SGT |
| SGD/EUR | MAS reference rate | Daily 09:00 SGT |
| SGD/GBP | MAS reference rate | Daily 09:00 SGT |
| SGD/MYR | MAS reference rate | Daily 09:00 SGT |
| SGD/CNY | MAS reference rate | Daily 09:00 SGT |
| Others | Bank buying/selling rate | As provided by bank |

---

# 11. Tax Handling Policies

## 11.1 GST Handling

> **GL mapping:** Policy `apply_tax_code` outputs logical codes (`SR`, `ZR`, …). **Authoritative COA mapping** is `tenant_tax_codes` in Client Admin (`15` §8.22 Tab 3, `06` §4.1c). Workers must not post GST to hard-coded `2100`/`1190` after `0.14.8` (`17` §3.2.3).

Policy: `gst_handling`

```json
{
  "policy": {
    "name": "gst_handling",
    "display_name": "GST Handling",
    "category": "tax",
    "description": "GST rate assignment and validation for Singapore",
    "rules": [
      {
        "rule_id": "uuid-130",
        "name": "standard_gst",
        "priority": 10,
        "description": "Standard-rated GST supplies",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "counterparty.name", "operator": "not_contains", "value": "overseas" },
            { "field": "case.amount_currency", "operator": "equals", "value": "SGD" }
          ]
        },
        "action": {
          "type": "apply_tax_code",
          "tax_code": "SR",
          "tax_rate": "0.09",
          "reason": "Standard-rated GST supply (9%)",
          "metadata": {
            "tax_account": "2105",
            "requires_gst_registration_check": true
          }
        }
      },
      {
        "rule_id": "uuid-131",
        "name": "zero_rated_export",
        "priority": 20,
        "description": "Zero-rated GST for exports",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "counterparty.country", "operator": "not_equals", "value": "SG" }
          ]
        },
        "action": {
          "type": "apply_tax_code",
          "tax_code": "ZR",
          "tax_rate": "0.00",
          "reason": "Zero-rated supply — export of goods/services"
        }
      },
      {
        "rule_id": "uuid-132",
        "name": "gst_exempt",
        "priority": 30,
        "description": "GST-exempt financial services",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "extraction.service_type", "operator": "in", "value": ["financial_services", "insurance"] }
          ]
        },
        "action": {
          "type": "apply_tax_code",
          "tax_code": "ES33",
          "tax_rate": "0.00",
          "reason": "GST-exempt financial service"
        }
      }
    ]
  }
}
```

## 11.2 Withholding Tax

Policy: `withholding_tax`

```json
{
  "policy": {
    "name": "withholding_tax",
    "display_name": "Withholding Tax",
    "category": "tax",
    "description": "Withholding tax on payments to non-residents",
    "rules": [
      {
        "rule_id": "uuid-140",
        "name": "wht_non_resident_services",
        "priority": 10,
        "description": "WHT on services payments to non-residents",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "counterparty.country", "operator": "not_equals", "value": "SG" },
            { "field": "extraction.service_type", "operator": "in", "value": ["professional_services", "technical_services"] }
          ]
        },
        "action": {
          "type": "apply_tax_code",
          "tax_code": "WHT-17",
          "tax_rate": "0.17",
          "reason": "Withholding tax on non-resident services (17%)",
          "risk_flags": ["withholding_tax_applies"]
        }
      }
    ]
  }
}
```

---

# 12. Reconciliation Tolerance Policies

## 12.1 Matching Tolerances

Policy: `matching_tolerances`

```json
{
  "policy": {
    "name": "matching_tolerances",
    "display_name": "Reconciliation Matching Tolerances",
    "category": "reconciliation",
    "description": "Tolerance levels for automatic bank reconciliation matching",
    "rules": [
      {
        "rule_id": "uuid-150",
        "name": "exact_match",
        "priority": 10,
        "description": "Exact match — amount, date, reference all align",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "match.amount_diff", "operator": "equals", "value": "0" },
            { "field": "match.date_diff_days", "operator": "equals", "value": "0" },
            { "field": "match.reference_match", "operator": "equals", "value": true }
          ]
        },
        "action": {
          "type": "auto_release",
          "reason": "Exact match — auto-confirm",
          "metadata": {
            "match_type": "exact",
            "confidence": 1.0
          }
        }
      },
      {
        "rule_id": "uuid-151",
        "name": "amount_date_match",
        "priority": 20,
        "description": "Same amount, within 3 days, no reference needed",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "match.amount_diff", "operator": "less_than_or_equal", "value": "0.01" },
            { "field": "match.date_diff_days", "operator": "less_than_or_equal", "value": "3" }
          ]
        },
        "action": {
          "type": "auto_release",
          "reason": "Amount and date match within tolerance — auto-confirm",
          "metadata": {
            "match_type": "tolerance",
            "confidence": 0.95
          }
        }
      },
      {
        "rule_id": "uuid-152",
        "name": "suspense_item",
        "priority": 50,
        "description": "Unmatched items go to suspense",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "match.match_found", "operator": "equals", "value": false }
          ]
        },
        "action": {
          "type": "escalate_review",
          "escalation_reason": "Unmatched bank/ledger item — requires manual review",
          "metadata": {
            "create_suspense_entry": true,
            "suspense_account": "1299"
          }
        }
      }
    ]
  }
}
```

## 12.2 Tolerance Matrix

| Match Type | Amount Tolerance | Date Tolerance | Reference Required | Auto-Confirm |
|-----------|-----------------|----------------|-------------------|--------------|
| Exact | SGD 0.00 | Same day | Yes | Yes |
| Tolerance A | SGD 0.01 | ±3 days | No | Yes |
| Tolerance B | SGD 1.00 | ±7 days | Partial | No (suggest) |
| Tolerance C | SGD 5.00 | ±14 days | Fuzzy | No (suggest) |
| No match | — | — | — | Route to suspense |

---

# 13. Policy Validation API

## 13.1 Validate Against Policies

```
POST /policies/validate
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Request:**

```json
{
  "case_type": "ap_invoice",
  "case_data": {
    "amount_value": "15850.00",
    "amount_currency": "SGD",
    "confidence_score": 0.94,
    "risk_flags": [],
    "counterparty": {
      "is_recurring": true,
      "type": "supplier"
    },
    "extraction": {
      "has_tax_breakdown": true,
      "document_completeness": 0.96,
      "has_po_reference": true
    }
  },
  "evaluate_categories": ["approval", "tax"]
}
```

**Response:**

```json
{
  "case_type": "ap_invoice",
  "evaluated_at": "2026-05-10T14:35:00Z",
  "results": [
    {
      "policy_id": "uuid-policy-001",
      "policy_name": "ap_approval_thresholds",
      "category": "approval",
      "version": "1.2.0",
      "matched": true,
      "matched_rule": {
        "rule_id": "uuid-002",
        "rule_name": "tier_2_standard_approval",
        "priority": 20
      },
      "action": {
        "type": "require_approval",
        "tier": 2,
        "reason": "Invoice amount SGD 15,850.00 requires finance officer approval",
        "risk_flags": ["amount_above_5k"],
        "sla_hours": 4
      },
      "evaluation_time_ms": 12
    },
    {
      "policy_id": "uuid-policy-002",
      "policy_name": "gst_handling",
      "category": "tax",
      "version": "1.0.0",
      "matched": true,
      "matched_rule": {
        "rule_id": "uuid-130",
        "rule_name": "standard_gst"
      },
      "action": {
        "type": "apply_tax_code",
        "tax_code": "SR",
        "tax_rate": "0.09",
        "reason": "Standard-rated GST supply (9%)"
      },
      "evaluation_time_ms": 8
    }
  ],
  "combined_action": {
    "type": "require_approval",
    "tier": 2,
    "reason": "Most restrictive action from evaluated policies",
    "risk_flags": ["amount_above_5k"],
    "sla_hours": 4,
    "tax_treatment": {
      "code": "SR",
      "rate": "0.09"
    }
  },
  "total_evaluation_time_ms": 23
}
```

## 13.2 Preview Policy Change

```
POST /policies/{id}/preview
Authorization: Bearer {jwt_token} (policies:write required)
```

**Request:**

```json
{
  "proposed_rule": {
    "name": "tier_2_standard_approval",
    "priority": 20,
    "conditions": {
      "operator": "AND",
      "conditions": [
        { "field": "case.amount_value", "operator": "less_than", "value": "75000" }
      ]
    },
    "action": {
      "type": "require_approval",
      "tier": 2
    }
  },
  "test_cases": [
    {
      "description": "SGD 60,000 invoice — currently tier 3, proposed tier 2",
      "case_data": {
        "amount_value": "60000",
        "amount_currency": "SGD",
        "confidence_score": 0.95,
        "risk_flags": [],
        "counterparty": { "is_recurring": true }
      }
    },
    {
      "description": "SGD 80,000 invoice — should remain tier 3",
      "case_data": {
        "amount_value": "80000",
        "amount_currency": "SGD",
        "confidence_score": 0.95,
        "risk_flags": [],
        "counterparty": { "is_recurring": true }
      }
    }
  ]
}
```

**Response:**

```json
{
  "proposed_change": {
    "rule_name": "tier_2_standard_approval",
    "change_summary": "Increase threshold from SGD 50,000 to SGD 75,000"
  },
  "test_results": [
    {
      "test_case": "SGD 60,000 invoice — currently tier 3, proposed tier 2",
      "current_result": { "tier": 3, "matched_rule": "tier_3_executive_approval" },
      "proposed_result": { "tier": 2, "matched_rule": "tier_2_standard_approval" },
      "impact": "DOWNGRADE: Would move from tier 3 to tier 2"
    },
    {
      "test_case": "SGD 80,000 invoice — should remain tier 3",
      "current_result": { "tier": 3, "matched_rule": "tier_3_executive_approval" },
      "proposed_result": { "tier": 3, "matched_rule": "tier_3_executive_approval" },
      "impact": "NO_CHANGE: Remains tier 3"
    }
  ],
  "affected_case_estimate": {
    "last_30_days": 12,
    "last_90_days": 34
  }
}
```

---

# 14. Policy Versioning & Audit

## 14.1 Version Management

| Operation | Behavior |
|-----------|----------|
| **Create** | New policy at version `1.0.0` |
| **Update rules** | Minor version bump (`1.0.0` → `1.1.0`) |
| **Change conditions fundamentally** | Major version bump (`1.1.0` → `2.0.0`) |
| **Deactivate** | Set `is_active = false`, `effective_to = today`. Policy remains queryable for historical cases. |
| **Supersede** | New policy references old via `superseded_by`. Old policy deactivated. |

## 14.2 Version Bump Rules

| Change Type | Version Bump | Example |
|-------------|-------------|---------|
| New rule added (non-breaking) | Minor | `1.0.0` → `1.1.0` |
| Rule priority changed | Minor | `1.0.0` → `1.1.0` |
| Rule condition tightened | Minor | `1.0.0` → `1.1.0` |
| Rule condition loosened | **Major** | `1.0.0` → `2.0.0` (may auto-approve more) |
| Rule removed | **Major** | `1.0.0` → `2.0.0` |
| Default action changed | **Major** | `1.0.0` → `2.0.0` |
| New policy category | Major | `1.0.0` → `2.0.0` |

## 14.3 Audit Trail

Every policy evaluation is logged:

```json
{
  "audit_type": "policy_evaluation",
  "case_id": "uuid",
  "policy_id": "uuid",
  "policy_name": "ap_approval_thresholds",
  "policy_version": "1.2.0",
  "rule_id": "uuid-002",
  "rule_name": "tier_2_standard_approval",
  "conditions_evaluated": { /* full condition tree with true/false per node */ },
  "result_action": { /* action output */ },
  "evaluation_time_ms": 12,
  "evaluated_at": "2026-05-10T14:35:00Z"
}
```

## 14.4 Immutable Snapshots

When a policy version is deactivated, a snapshot is stored in `policy_versions`:

```sql
INSERT INTO policy_versions (policy_id, version, rules_snapshot, changed_by, change_summary)
VALUES ('policy-uuid', '1.2.0', '{full rules JSON}', 'user-uuid', 'Increased tier 2 threshold from 30k to 50k');
```

This allows historical cases to reference the exact policy version that was active at the time.

---

# 15. Default Policy Configuration (Seed Data)

## 15.1 Seed Order

Policies are seeded during Phase 4 (Workflow Orchestrator + Policy Engine Scaffold):

```sql
-- 1. Approval policies
INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('ap_approval_thresholds', 'AP Approval Thresholds', 'approval', '1.0.0', true, '2026-01-01', 'system');

INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('ar_approval_thresholds', 'AR Approval Thresholds', 'approval', '1.0.0', true, '2026-01-01', 'system');

INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('journal_posting_authority', 'Journal Posting Authority', 'approval', '1.0.0', true, '2026-01-01', 'system');

-- 2. Accounting policies
INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('revenue_recognition_timing', 'Revenue Recognition Timing', 'accounting', '1.0.0', true, '2026-01-01', 'system');

INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('expense_recognition_rules', 'Expense Recognition Rules', 'accounting', '1.0.0', true, '2026-01-01', 'system');

INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('fx_transaction_handling', 'FX Transaction Handling', 'accounting', '1.0.0', true, '2026-01-01', 'system');

INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('duplicate_detection_rules', 'Duplicate Detection Rules', 'accounting', '1.0.0', true, '2026-01-01', 'system');

-- 3. Tax policies
INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('gst_handling', 'GST Handling', 'tax', '1.0.0', true, '2026-01-01', 'system');

INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('withholding_tax', 'Withholding Tax', 'tax', '1.0.0', true, '2026-01-01', 'system');

INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('tax_code_assignment', 'Tax Code Assignment', 'tax', '1.0.0', true, '2026-01-01', 'system');

-- 4. Reconciliation policies
INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('matching_tolerances', 'Matching Tolerances', 'reconciliation', '1.0.0', true, '2026-01-01', 'system');

INSERT INTO policies (name, display_name, category, version, is_active, effective_from, created_by)
VALUES ('suspense_account_handling', 'Suspense Account Handling', 'reconciliation', '1.0.0', true, '2026-01-01', 'system');
```

## 15.2 Duplicate Detection Policy

Policy: `duplicate_detection_rules`

```json
{
  "policy": {
    "name": "duplicate_detection_rules",
    "display_name": "Duplicate Detection Rules",
    "category": "accounting",
    "description": "How to detect and handle potential duplicate invoices",
    "rules": [
      {
        "rule_id": "uuid-160",
        "name": "exact_duplicate",
        "priority": 10,
        "description": "Same invoice number, same supplier, same amount within 30 days",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "duplicate_check.invoice_number_match", "operator": "equals", "value": true },
            { "field": "duplicate_check.supplier_match", "operator": "equals", "value": true },
            { "field": "duplicate_check.amount_match", "operator": "equals", "value": true },
            { "field": "duplicate_check.days_apart", "operator": "less_than_or_equal", "value": "30" }
          ]
        },
        "action": {
          "type": "reject",
          "reason": "Duplicate invoice detected — same invoice number from same supplier within 30 days",
          "category": "duplicate_submission"
        }
      },
      {
        "rule_id": "uuid-161",
        "name": "suspected_duplicate",
        "priority": 20,
        "description": "Same supplier, same amount, different invoice number within 7 days",
        "conditions": {
          "operator": "AND",
          "conditions": [
            { "field": "duplicate_check.invoice_number_match", "operator": "equals", "value": false },
            { "field": "duplicate_check.supplier_match", "operator": "equals", "value": true },
            { "field": "duplicate_check.amount_match", "operator": "equals", "value": true },
            { "field": "duplicate_check.days_apart", "operator": "less_than_or_equal", "value": "7" }
          ]
        },
        "action": {
          "type": "flag_risk",
          "risk_flags": ["suspected_duplicate"],
          "action": "hold",
          "reason": "Potential duplicate — same supplier and amount within 7 days with different invoice number"
        }
      }
    ]
  }
}
```

---

# 16. Implementation Reference (Python)

## 16.1 Condition Evaluator

```python
# app/core/policy_engine.py

import re
from typing import Any, Optional
from datetime import datetime, timezone
from decimal import Decimal


class ConditionEvaluator:
    """
    Evaluates policy conditions against a case context.
    Pure functions — no side effects, no database access.
    """
    
    def evaluate(self, condition: dict, context: dict) -> bool:
        """
        Evaluate a condition (simple or compound) against context.
        """
        operator = condition.get("operator")
        
        # Compound conditions
        if operator == "AND":
            return all(
                self.evaluate(c, context) for c in condition.get("conditions", [])
            )
        
        if operator == "OR":
            return any(
                self.evaluate(c, context) for c in condition.get("conditions", [])
            )
        
        if operator == "NOT":
            return not self.evaluate(condition.get("conditions", {})[0], context)
        
        # Simple condition
        return self._evaluate_simple(condition, context)
    
    def _evaluate_simple(self, condition: dict, context: dict) -> bool:
        field_path = condition["field"]
        operator = condition["operator"]
        expected_value = condition.get("value")
        
        actual_value = self._resolve_field(field_path, context)
        
        # Handle null
        if actual_value is None:
            if operator == "is_empty":
                return True
            if operator == "is_not_empty":
                return False
            if operator == "equals" and expected_value is None:
                return True
            return False
        
        # Type coercion for numeric comparisons
        if operator in ("greater_than", "greater_than_or_equal", "less_than", 
                        "less_than_or_equal", "between") and isinstance(expected_value, str):
            expected_value = Decimal(expected_value)
            actual_value = Decimal(str(actual_value))
        
        # Dispatch
        evaluators = {
            "equals": lambda a, e: a == e,
            "not_equals": lambda a, e: a != e,
            "greater_than": lambda a, e: a > e,
            "greater_than_or_equal": lambda a, e: a >= e,
            "less_than": lambda a, e: a < e,
            "less_than_or_equal": lambda a, e: a <= e,
            "between": lambda a, e: e[0] <= a <= e[1],
            "contains": lambda a, e: e in (a or []),
            "not_contains": lambda a, e: e not in (a or []),
            "is_empty": lambda a, _: not bool(a) if a is not None else True,
            "is_not_empty": lambda a, _: bool(a) if a is not None else False,
            "in": lambda a, e: a in e,
            "starts_with": lambda a, e: str(a).startswith(str(e)),
            "ends_with": lambda a, e: str(a).endswith(str(e)),
            "matches_regex": lambda a, e: bool(re.match(e, str(a))),
        }
        
        evaluator = evaluators.get(operator)
        if not evaluator:
            raise ValueError(f"Unknown operator: {operator}")
        
        return evaluator(actual_value, expected_value)
    
    def _resolve_field(self, field_path: str, context: dict) -> Any:
        """
        Resolve a dot-notation field path against the context.
        Returns None if path doesn't exist.
        """
        parts = field_path.split(".")
        current = context
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current


class PolicyEngine:
    """
    Evaluates cases against policies and returns actions.
    """
    
    def __init__(self, condition_evaluator: ConditionEvaluator):
        self.evaluator = condition_evaluator
        self._action_rank = {
            "reject": 1,
            "escalate_review": 2,
            "require_approval": 3,
            "require_document": 4,
            "flag_risk": 5,
            "auto_release": 6,
            "apply_tax_code": 7,          # enrichment — does not block
            "assign_journal_template": 8,  # enrichment — does not block
        }
    
    def evaluate_policy(self, policy: dict, context: dict) -> dict:
        """
        Evaluate a single policy against case context.
        Returns the first matching rule's action, or default action.
        """
        rules = sorted(
            [r for r in policy.get("rules", []) if r.get("is_active", True)],
            key=lambda r: r.get("priority", 100)
        )
        
        for rule in rules:
            conditions = rule.get("conditions", {})
            
            try:
                if self.evaluator.evaluate(conditions, context):
                    return {
                        "matched": True,
                        "matched_rule": rule,
                        "action": rule["action"],
                        "reason": f"Matched rule: {rule.get('name', 'unknown')}"
                    }
            except Exception as e:
                # Log condition evaluation error, continue to next rule
                continue
        
        # No rule matched — return default
        return {
            "matched": False,
            "matched_rule": None,
            "action": policy.get("default_action", {
                "type": "require_approval",
                "tier": 2,
                "reason": "No matching rule — default approval required"
            }),
            "reason": "No rule matched — using default action"
        }
    
    def combine_results(self, results: list[dict]) -> dict:
        """
        Combine results from multiple policies.
        Most restrictive action wins.
        """
        if not results:
            return {
                "type": "require_approval",
                "tier": 2,
                "reason": "No policies evaluated"
            }
        
        def action_rank(result):
            action = result.get("action", {})
            base_rank = self._action_rank.get(action.get("type"), 99)
            # Lower tier numbers are more restrictive within require_approval
            if action.get("type") == "require_approval":
                tier = action.get("tier", 2)
                return base_rank * 10 + (4 - tier)  # tier 3 = rank 3*10+1=31, tier 2 = 32
            return base_rank * 10
        
        most_restrictive = min(results, key=action_rank)
        
        # Merge risk flags from all results
        all_risk_flags = set()
        for r in results:
            flags = r.get("action", {}).get("risk_flags", [])
            all_risk_flags.update(flags)
        
        combined_action = dict(most_restrictive["action"])
        combined_action["risk_flags"] = sorted(all_risk_flags)
        
        return combined_action
```

## 16.2 Policy Service

```python
# app/services/policy_service.py

from app.core.policy_engine import PolicyEngine, ConditionEvaluator
from app.repositories.policy_repository import PolicyRepository
from app.repositories.audit_repository import AuditRepository


class PolicyService:
    def __init__(
        self,
        policy_repo: PolicyRepository,
        audit_repo: AuditRepository,
        engine: PolicyEngine,
    ):
        self.policy_repo = policy_repo
        self.audit_repo = audit_repo
        self.engine = engine
    
    async def evaluate_case(self, case_data: CaseData) -> EvaluationResult:
        """
        Evaluate a case against all relevant active policies.
        Returns combined result and logs evaluation.
        """
        # Build context
        context = self._build_context(case_data)
        
        # Get relevant policies
        policies = await self.policy_repo.get_active_for_case_type(case_data.type)
        
        # Evaluate each policy
        results = []
        for policy in policies:
            result = self.engine.evaluate_policy(policy, context)
            results.append(result)
            
            # Audit individual policy evaluation
            await self.audit_repo.create_policy_evaluation(
                case_id=case_data.id,
                policy_id=policy["id"],
                policy_name=policy["name"],
                policy_version=policy["version"],
                rule_id=result.get("matched_rule", {}).get("rule_id") if result["matched"] else None,
                result_action=result["action"],
                conditions_evaluated=result.get("matched_rule", {}).get("conditions") if result["matched"] else None,
            )
        
        # Combine results
        combined = self.engine.combine_results(results)
        
        return EvaluationResult(
            matched=any(r["matched"] for r in results),
            action=combined,
            policy_results=results,
        )
    
    async def preview_policy_change(
        self,
        policy_id: uuid.UUID,
        proposed_rule: dict,
        test_cases: list[dict]
    ) -> dict:
        """
        Preview the impact of a proposed policy change on test cases.
        Does NOT persist any changes.
        """
        policy = await self.policy_repo.get(policy_id)
        
        results = []
        for test in test_cases:
            # Current result
            current_context = self._build_context_from_dict(test["case_data"])
            current_result = self.engine.evaluate_policy(policy, current_context)
            
            # Proposed result — temporarily swap rule
            modified_policy = dict(policy)
            modified_rules = [r for r in modified_policy["rules"] 
                            if r["rule_id"] != proposed_rule.get("rule_id")]
            modified_rules.append(proposed_rule)
            modified_policy["rules"] = modified_rules
            
            proposed_result = self.engine.evaluate_policy(modified_policy, current_context)
            
            results.append({
                "test_case": test["description"],
                "current_result": current_result["action"],
                "proposed_result": proposed_result["action"],
                "impact": self._compare_actions(
                    current_result["action"], 
                    proposed_result["action"]
                )
            })
        
        return {
            "proposed_change": {
                "rule_name": proposed_rule["name"],
                "change_summary": self._summarize_change(proposed_rule)
            },
            "test_results": results
        }
    
    def _build_context(self, case_data: CaseData) -> dict:
        """Build evaluation context from case data."""
        return {
            "case": {
                "type": case_data.type,
                "status": case_data.status,
                "priority": case_data.priority,
                "amount_value": str(case_data.amount_value) if case_data.amount_value else None,
                "amount_currency": case_data.amount_currency,
                "confidence_score": str(case_data.confidence_score) if case_data.confidence_score else None,
                "risk_flags": case_data.risk_flags or [],
                "tags": case_data.tags or [],
                "stp_eligible": case_data.stp_eligible,
            },
            "counterparty": {
                "is_recurring": case_data.counterparty.is_recurring if case_data.counterparty else False,
                "type": case_data.counterparty.type if case_data.counterparty else None,
            } if case_data.counterparty else {},
            "extraction": case_data.extraction_data or {},
            "ai": case_data.classification_metadata or {},
            "now": datetime.now(timezone.utc).isoformat(),
        }
    
    def _compare_actions(self, current: dict, proposed: dict) -> str:
        """Compare two actions and return impact description."""
        if current == proposed:
            return "NO_CHANGE"
        
        restrictiveness = {
            "reject": 1, "escalate_review": 2, "require_approval": 3,
            "require_document": 4, "flag_risk": 5, "auto_release": 6,
            "apply_tax_code": 7, "assign_journal_template": 8,
        }
        
        curr_rank = restrictiveness.get(current.get("type"), 99)
        prop_rank = restrictiveness.get(proposed.get("type"), 99)
        
        if prop_rank < curr_rank:
            return f"ESCALATE: {current.get('type')} → {proposed.get('type')}"
        elif prop_rank > curr_rank:
            return f"DOWNGRADE: {current.get('type')} → {proposed.get('type')}"
        else:
            return f"MODIFIED: Same action type, different parameters"
```

## 16.3 FastAPI Routes

```python
# app/api/routes/policies.py

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/policies")


@router.post("/validate")
async def validate_against_policies(
    request: ValidatePolicyRequest,
    current_user: User = Depends(get_current_user),
    service: PolicyService = Depends(get_policy_service),
):
    """Validate case data against active policies (dry-run)."""
    result = await service.evaluate_case(
        CaseData(
            type=request.case_type,
            amount_value=Decimal(request.case_data.get("amount_value", 0)),
            amount_currency=request.case_data.get("amount_currency", "SGD"),
            confidence_score=request.case_data.get("confidence_score"),
            risk_flags=request.case_data.get("risk_flags", []),
            counterparty=CounterpartyData(
                is_recurring=request.case_data.get("counterparty", {}).get("is_recurring", False),
            ) if request.case_data.get("counterparty") else None,
            extraction_data=request.case_data.get("extraction"),
        )
    )
    
    return {
        "case_type": request.case_type,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "combined_action": result.action,
        "evaluation_time_ms": result.evaluation_time_ms,
    }


@router.post("/{policy_id}/preview")
async def preview_policy_change(
    policy_id: uuid.UUID,
    request: PreviewPolicyRequest,
    current_user: User = Depends(require_permission("policies:write")),
    service: PolicyService = Depends(get_policy_service),
):
    """Preview impact of proposed policy change."""
    return await service.preview_policy_change(
        policy_id=policy_id,
        proposed_rule=request.proposed_rule.dict(),
        test_cases=[tc.dict() for tc in request.test_cases]
    )
```

## 16.4 Tests

```python
# tests/test_policy_engine.py

import pytest
from decimal import Decimal
from app.core.policy_engine import ConditionEvaluator, PolicyEngine


class TestConditionEvaluator:
    @pytest.fixture
    def evaluator(self):
        return ConditionEvaluator()
    
    @pytest.fixture
    def context(self):
        return {
            "case": {
                "amount_value": "15850.00",
                "type": "ap_invoice",
                "risk_flags": ["amount_above_10k"]
            },
            "counterparty": {
                "is_recurring": True
            }
        }
    
    def test_equals(self, evaluator, context):
        assert evaluator.evaluate(
            {"field": "case.type", "operator": "equals", "value": "ap_invoice"},
            context
        )
    
    def test_less_than(self, evaluator, context):
        assert evaluator.evaluate(
            {"field": "case.amount_value", "operator": "less_than", "value": "50000"},
            context
        )
    
    def test_contains(self, evaluator, context):
        assert evaluator.evaluate(
            {"field": "case.risk_flags", "operator": "contains", "value": "amount_above_10k"},
            context
        )
    
    def test_and_compound(self, evaluator, context):
        assert evaluator.evaluate(
            {
                "operator": "AND",
                "conditions": [
                    {"field": "case.amount_value", "operator": "less_than", "value": "50000"},
                    {"field": "counterparty.is_recurring", "operator": "equals", "value": True}
                ]
            },
            context
        )
    
    def test_missing_field_returns_none(self, evaluator, context):
        result = evaluator._resolve_field("case.nonexistent", context)
        assert result is None
    
    def test_is_empty_on_missing_field(self, evaluator, context):
        assert evaluator.evaluate(
            {"field": "case.nonexistent_array", "operator": "is_empty"},
            context
        )


class TestPolicyEngine:
    @pytest.fixture
    def engine(self):
        return PolicyEngine(ConditionEvaluator())
    
    def test_first_match_wins(self, engine):
        policy = {
            "rules": [
                {
                    "rule_id": "1",
                    "priority": 10,
                    "name": "high_value",
                    "conditions": {"field": "amount", "operator": "greater_than", "value": "1000"},
                    "action": {"type": "require_approval", "tier": 2}
                },
                {
                    "rule_id": "2",
                    "priority": 20,
                    "name": "any_value",
                    "conditions": {"field": "amount", "operator": "greater_than", "value": "0"},
                    "action": {"type": "auto_release"}
                }
            ],
            "default_action": {"type": "require_approval", "tier": 2}
        }
        
        result = engine.evaluate_policy(policy, {"amount": "5000"})
        assert result["matched"]
        assert result["action"]["type"] == "require_approval"
        assert result["matched_rule"]["name"] == "high_value"
    
    def test_default_action_when_no_match(self, engine):
        policy = {
            "rules": [
                {
                    "rule_id": "1",
                    "priority": 10,
                    "conditions": {"field": "amount", "operator": "greater_than", "value": "100000"},
                    "action": {"type": "require_approval", "tier": 3}
                }
            ],
            "default_action": {"type": "auto_release"}
        }
        
        result = engine.evaluate_policy(policy, {"amount": "5000"})
        assert not result["matched"]
        assert result["action"]["type"] == "auto_release"
    
    def test_combine_results_most_restrictive(self, engine):
        results = [
            {"action": {"type": "auto_release"}},
            {"action": {"type": "require_approval", "tier": 2}},
            {"action": {"type": "flag_risk", "risk_flags": ["test"]}},
        ]
        
        combined = engine.combine_results(results)
        assert combined["type"] == "require_approval"
        assert combined["tier"] == 2
    
    def test_combine_merges_risk_flags(self, engine):
        results = [
            {"action": {"type": "auto_release", "risk_flags": ["flag1"]}},
            {"action": {"type": "auto_release", "risk_flags": ["flag2"]}},
        ]
        
        combined = engine.combine_results(results)
        assert "flag1" in combined["risk_flags"]
        assert "flag2" in combined["risk_flags"]
```

---

# 17. Testing Strategy

## 17.1 Unit Tests

| Test Category | Coverage Target | Framework |
|---------------|----------------|-----------|
| Condition evaluator operators | 100% of operators | pytest |
| Compound condition logic | AND, OR, NOT combinations | pytest |
| Field resolution | Missing fields, nested paths | pytest |
| Action restrictiveness ranking | All action types | pytest |
| Rule priority ordering | Multiple rules, same/different priorities | pytest |

## 17.2 Integration Tests

| Test Scenario | Description |
|---------------|-------------|
| Full policy evaluation | Load policy from DB, evaluate realistic case data |
| Multi-policy combination | Approval + tax policies evaluated together |
| Policy change preview | Verify preview endpoint shows correct impact |
| Audit logging | Confirm every evaluation is logged |
| Performance | < 50ms for 10 rules with compound conditions |

## 17.3 Acceptance Tests

| Scenario | Input | Expected Output |
|----------|-------|-----------------|
| SGD 3,000 invoice from recurring supplier | Amount: 3000, recurring: true, risk_flags: [] | `auto_release` |
| SGD 15,000 invoice from recurring supplier | Amount: 15850, recurring: true, risk_flags: [] | `require_approval` tier 2 |
| SGD 60,000 invoice from new supplier | Amount: 60000, recurring: false, risk_flags: [] | `require_approval` tier 3 |
| Invoice missing tax breakdown | Amount: 5000, has_tax_breakdown: false | `require_document` |
| Duplicate invoice detected | Same inv# + supplier + amount within 7 days | `reject` |
| Foreign currency invoice | Amount: 10000 USD | `apply_tax_code` + FX conversion + approval |

---

# Appendix A: Condition Operator Quick Reference

| Operator | Types | Example |
|----------|-------|---------|
| `equals` | string, number, bool | `field = "ap_invoice"` |
| `not_equals` | string, number, bool | `field != "exception"` |
| `greater_than` | number | `field > 5000` |
| `greater_than_or_equal` | number | `field >= 0.90` |
| `less_than` | number | `field < 50000` |
| `less_than_or_equal` | number | `field <= 3` |
| `between` | number[2] | `5000 <= field <= 50000` |
| `contains` | string (in array) | `"flag" in field` |
| `not_contains` | string (in array) | `"flag" not in field` |
| `is_empty` | array, string | `not field` |
| `is_not_empty` | array, string | `bool(field)` |
| `in` | string (in set) | `field in ["a", "b"]` |
| `starts_with` | string | `field.startswith("INV-")` |
| `ends_with` | string | `field.endswith("Pte Ltd")` |
| `matches_regex` | string | `re.match(pattern, field)` |

---

# Appendix B: Action Type Quick Reference

| Action Type | Restrictiveness | Parameters | Description |
|-------------|----------------|------------|-------------|
| `reject` | 1 (highest) | `reason`, `category` | Permanently reject |
| `escalate_review` | 2 | `escalation_reason` | Send to manual review |
| `require_approval` | 3 | `tier`, `sla_hours` | Route to approval |
| `require_document` | 4 | `document_type`, `reason` | Request additional doc |
| `flag_risk` | 5 | `risk_flags[]`, `action` | Add flags, continue/hold |
| `auto_release` | 6 | `posting_account` | Full STP |
| `apply_tax_code` | 7 | `tax_code`, `tax_rate` | Assign tax treatment (does not block; enriches case) |
| `assign_journal_template` | 8 (lowest) | `template_id` | Use specific journal entry template (does not block; enriches case) |

> **Note:** `apply_tax_code` and `assign_journal_template` are enrichment actions — they do not block or hold a case. In `combine_results()`, they are always overridden by any blocking action (ranks 1–5). If the combined result is `auto_release` (rank 6), enrichment actions in ranks 7–8 are applied additively. See §16 `_compare_actions` for the implementation.

---

# Appendix C: Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.2.0 | 2026-05-17 | Fix (m-5 from cross-document audit): Added scope clarification note to §9 heading — distinguishes AP invoice expense recognition (§9, this document) from employee expense claim policy validation (`19_Expense_Worker_Specification.md` §5, `expense_policies` table). No content changes; the two mechanisms are independent and there is no conflict. The note prevents developer confusion when reading both documents side-by-side during Phase 11 implementation. |
| 1.1.0 | 2026-05-15 | Fix (Issue 2 from audit): Added `apply_tax_code` (rank 7) and `assign_journal_template` (rank 8) to Appendix B Action Type Quick Reference. These two enrichment action types were defined in §4.2 Action Types table but were missing from Appendix B and from the `_action_rank` dict in `PolicyEngine.__init__` and the `restrictiveness` dict in `_compare_actions` (§16). All three locations now list all 8 action types, consistent with the "8 action types" claim in `00` §3.3 and `10` header. Added clarifying note to Appendix B explaining that enrichment actions (ranks 7–8) do not block cases and are applied additively when the combined result is `auto_release`. |
| 1.0.0 | 2026-05-11 | Initial release — complete policy engine with condition language, action language, 10 default policies, Python implementation, and testing strategy |

---

# Appendix D: Notes for Cursor Implementation

1. **Policy rules are data, not code** — Store them in the `policy_rules` table as JSONB. Never hardcode rules in Python. The engine reads rules from the database at startup and caches them.

2. **Cache active policies** — Load active policies into memory at startup. Invalidate cache when a policy is updated (use Redis pub/sub for cache invalidation). Target: < 10ms evaluation time.

3. **Never auto-approve by default** — The default action for every policy category is `require_approval` tier 2. Only explicit rules can grant `auto_release`. This is a safety principle.

4. **Test policy changes in preview first** — Always use the `/policies/{id}/preview` endpoint before deploying a policy change. The preview shows exactly which cases would be affected.

5. **Log every evaluation** — The audit log must contain the full evaluation context: which policy, which version, which rule matched, what the conditions evaluated to. This is non-negotiable for compliance.

6. **Version bump on any loosening** — If a change would auto-approve more cases (raise a threshold, remove a condition), bump the major version. This triggers a governance review.

7. **Keep the evaluator pure** — `ConditionEvaluator` has no database access, no external calls, no side effects. It receives a context dict and returns a boolean. This makes it trivially testable.

8. **Use Decimal for money comparisons** — All numeric comparisons in conditions use `Decimal`, never float. Prevents floating-point precision issues with monetary amounts.

9. **Field paths are flat in the context** — The dot-notation `case.amount_value` resolves to `context["case"]["amount_value"]`. The context builder flattens relational data into nested dicts before evaluation.

10. **Policy change requires `policies:write` + admin review** — The API enforces RBAC. Policy changes also create audit entries and optionally notify finance managers via SSE.
