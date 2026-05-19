# Dapr Workflow — Context Propagation (Python SDK)

This quickstart demonstrates **workflow history propagation**, a new feature in Dapr 1.18 that lets a parent workflow share its execution history with child workflows and activities. Downstream services can inspect that history to make trust-aware decisions — without any external state store or custom messaging.

> **Runtime requirement**: Dapr 1.18+ ([dapr/dapr#9810](https://github.com/dapr/dapr/pull/9810))  
> **SDK requirement**: `dapr-ext-workflow>=1.18.0rc0` ([dapr/python-sdk#1025](https://github.com/dapr/python-sdk/pull/1025))  
> **Proposal**: [dapr/proposals#102](https://github.com/dapr/proposals/issues/102)

## What is workflow context propagation?

When a parent workflow calls a child workflow or activity it can optionally attach a tamper-evident snapshot of its own execution history. The receiver reads that snapshot via `ctx.get_propagated_history()` and queries it by workflow name and activity name — letting it verify that the correct upstream steps ran before it proceeds.

### Two propagation modes

| Mode | Constant | What the receiver sees |
|------|----------|----------------------|
| **Own history** | `PropagationScope.OWN_HISTORY` | Only the direct caller's events |
| **Lineage** | `PropagationScope.LINEAGE` | Caller's events **plus** any ancestor history the caller itself received |

## Scenario: Credit-card payment with fraud detection

```
MerchantCheckout (root)
  └─ validate_merchant         (activity, no propagation)
  └─ ProcessPayment            (child wf, LINEAGE)
        └─ validate_card       (activity, no propagation)
        └─ check_spending_limits (activity, no propagation)
        └─ FraudDetection      (grandchild wf, LINEAGE)
        |      reads MerchantCheckout/validate_merchant
        |            ProcessPayment/validate_card
        |            ProcessPayment/check_spending_limits
        └─ settle_payment      (activity, OWN_HISTORY)
               reads ProcessPayment events only
```

`FraudDetection` uses `PropagationScope.LINEAGE` to see the **full ancestor chain** — it can verify both the merchant validation (performed by the grandparent) and the card/limit checks (performed by the parent) before approving the transaction.

`settle_payment` uses `PropagationScope.OWN_HISTORY` to see only the **direct caller's events** — a trust-boundary mode that limits visibility to what `ProcessPayment` itself executed.

## Python API surface

```python
# Parent workflow — propagate LINEAGE when calling a child workflow
result = yield ctx.call_child_workflow(
    fraud_detection,
    input=req_json,
    propagation=wf.PropagationScope.LINEAGE,
)

# Parent workflow — propagate OWN_HISTORY when calling an activity
settlement = yield ctx.call_activity(
    settle_payment,
    input=req_json,
    propagation=wf.PropagationScope.OWN_HISTORY,
)

# Child workflow (or activity) — read the propagated history
history = ctx.get_propagated_history()   # returns PropagatedHistory | None

if history is not None:
    process_wf = history.get_workflow_by_name('ProcessPayment')   # raises PropagationNotFoundError if missing
    card_act    = process_wf.get_activity_by_name('validate_card')
    print(card_act.completed)   # bool
    print(card_act.output)      # JSON string
```

Key types exported from `dapr.ext.workflow`:
- `PropagationScope` — enum with `LINEAGE` and `OWN_HISTORY`
- `PropagatedHistory` — top-level history object; call `.get_workflows()` or `.get_workflow_by_name(name)`
- `WorkflowResult` — per-workflow slice; call `.get_activity_by_name(name)` or `.get_child_workflow_by_name(name)`
- `ActivityResult` — has `.completed`, `.output` fields
- `PropagationNotFoundError` — raised when a named workflow/activity is not in the history

## Prerequisites

- [Dapr CLI](https://docs.dapr.io/getting-started/install-dapr-cli/) 1.18+
- Dapr runtime 1.18+ initialized (`dapr init`)
- Python 3.9+
- Redis (started automatically by `dapr init`)

## Run the sample

```sh
cd workflows/python/sdk-context-propagation

# Install dependencies
pip3 install -r order-processor/requirements.txt

# Run with Dapr
dapr run -f .
```

## Expected output

```
============================================
= WORKFLOW HISTORY PROPAGATION DEMO =
============================================

  Flow: MerchantCheckout -> validate_merchant
           -> ProcessPayment (child wf, LINEAGE)
               -> validate_card -> check_spending_limits
               -> FraudDetection (child wf, LINEAGE)    <-- sees MerchantCheckout + ProcessPayment events
               -> settle_payment (activity, OWN_HISTORY) <-- sees only ProcessPayment events

  [main] Started workflow instance: checkout-001
  [MerchantCheckout] Starting checkout for merchant merchant-abc
  [MerchantCheckout] Step 1: validate_merchant (no propagation)
  [ValidateMerchant] Validating merchant merchant-abc
  [MerchantCheckout] Step 1 complete: merchant valid
  [MerchantCheckout] Step 2: ProcessPayment child wf (PropagationScope.LINEAGE)
  [ProcessPayment] Starting payment ****4242 149.99 USD
  [ProcessPayment] Step 1: validate_card (no propagation)
  [ValidateCard] Validating card ****4242 (propagated history: none)
  [ProcessPayment] Step 1 complete: card valid
  [ProcessPayment] Step 2: check_spending_limits (no propagation)
  [CheckSpendingLimits] Checking 149.99 USD (propagated history: none)
  [ProcessPayment] Step 2 complete: within limits
  [ProcessPayment] Step 3: FraudDetection child wf (PropagationScope.LINEAGE)
  [FraudDetection] Received propagated history with workflows: ['MerchantCheckout', 'ProcessPayment']
  [FraudDetection] Verification:
    MerchantCheckout/validate_merchant: completed=True
    ProcessPayment/validate_card:        completed=True
    ProcessPayment/check_spending_limits: completed=True
  [FraudDetection] APPROVED (risk=0.10)
  [ProcessPayment] Step 3 complete: fraud check passed (risk=0.10)
  [ProcessPayment] Step 4: settle_payment (PropagationScope.OWN_HISTORY)
  [SettlePayment] Propagated workflows: ['ProcessPayment']
  [SettlePayment] SETTLED: txn-merchant-abc-1748000000000
  [ProcessPayment] Step 4 complete: settled (txn=txn-merchant-abc-...)
  [ProcessPayment] COMPLETE: payment settled: ...
  [MerchantCheckout] COMPLETE: payment settled: ...
  [main] Workflow completed! Output: "payment settled: ..."

========================
= COMPLETE =
========================
```

## Stop the sample

```sh
dapr stop -f .
```

## References

- [Proposal: Workflow History Propagation (dapr/proposals#102)](https://github.com/dapr/proposals/issues/102)
- [Runtime PR: dapr/dapr#9810](https://github.com/dapr/dapr/pull/9810)
- [Python SDK PR: dapr/python-sdk#1025](https://github.com/dapr/python-sdk/pull/1025)
- [Go SDK reference: dapr/go-sdk#823](https://github.com/dapr/go-sdk/pull/823)
- [Dapr Workflow documentation](https://docs.dapr.io/developing-applications/building-blocks/workflow/)
