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

## Scenario: Patient intake / e-prescribing

A compliance audit and a pharmacy dispense step refuse to act unless the propagated history proves the required upstream checks (insurance, allergies, drug interactions) actually ran.

```
PatientIntake (root)
  └─ VerifyInsurance       (activity, no propagation)
  └─ PrescribeMedication   (child wf, LINEAGE)
        └─ CheckAllergies         (activity, no propagation)
        └─ ScreenDrugInteractions (activity, no propagation)
        └─ ComplianceAudit        (grandchild wf, LINEAGE)
        |      reads PatientIntake/VerifyInsurance
        |            PrescribeMedication/CheckAllergies
        |            PrescribeMedication/ScreenDrugInteractions
        └─ DispenseMedication     (activity, OWN_HISTORY)
               reads PrescribeMedication events only
```

`ComplianceAudit` uses `PropagationScope.LINEAGE` to see the **full ancestor chain** — it can verify both the insurance check (performed by the grandparent `PatientIntake`) and the allergy/interaction checks (performed by the parent `PrescribeMedication`) before approving the prescription.

`DispenseMedication` uses `PropagationScope.OWN_HISTORY` to see only the **direct caller's events** — a trust-boundary mode that limits visibility to what `PrescribeMedication` itself executed. The pharmacy dispense system doesn't need (or get to see) the upstream patient-intake chain.

This sample mirrors the canonical Go reference [dapr/go-sdk#823](https://github.com/dapr/go-sdk/pull/823) and the [Go quickstart](https://github.com/dapr/quickstarts/pull/1315).

## Python API surface

```python
# Parent workflow — propagate LINEAGE when calling a child workflow
result = yield ctx.call_child_workflow(
    compliance_audit,
    input=rec_json,
    propagation=wf.PropagationScope.LINEAGE,
)

# Parent workflow — propagate OWN_HISTORY when calling an activity
dispense = yield ctx.call_activity(
    dispense_medication,
    input=rec_json,
    propagation=wf.PropagationScope.OWN_HISTORY,
)

# Child workflow (or activity) — read the propagated history
history = ctx.get_propagated_history()   # returns PropagatedHistory | None

if history is not None:
    intake_wf  = history.get_workflow_by_name('PatientIntake')   # raises PropagationNotFoundError if missing
    insurance  = intake_wf.get_activity_by_name('VerifyInsurance')
    print(insurance.completed)   # bool
    print(insurance.output)      # JSON string
```

Key types exported from `dapr.ext.workflow`:
- `PropagationScope` — enum with `LINEAGE` and `OWN_HISTORY`
- `PropagatedHistory` — top-level history object; call `.get_workflows()` or `.get_workflow_by_name(name)`
- `WorkflowResult` — per-workflow slice; call `.get_activity_by_name(name)` or `.get_child_workflow_by_name(name)`
- `ActivityResult` — has `.completed`, `.output` fields
- `PropagationNotFoundError` — raised when a named workflow/activity is not in the history

> **Replay safety**: workflow code runs many times during durable execution. Guard side-effecting calls — including `print()` — with `if not ctx.is_replaying:` so they only fire on the live execution, not on each replay.

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
============================================================
= WORKFLOW HISTORY PROPAGATION DEMO — PATIENT INTAKE =
============================================================

  Flow: PatientIntake -> VerifyInsurance
           -> PrescribeMedication (child wf, LINEAGE)
               -> CheckAllergies -> ScreenDrugInteractions
               -> ComplianceAudit (child wf, LINEAGE)        <-- sees PatientIntake + PrescribeMedication events
               -> DispenseMedication (activity, OWN_HISTORY) <-- sees only PrescribeMedication events

  [main] Started workflow instance: intake-001
  [PatientIntake] Starting intake for patient P-1042
  [PatientIntake] Step 1: VerifyInsurance (no propagation)
  [VerifyInsurance] Checking coverage for patient P-1042
  [PatientIntake] Step 1 complete: insurance verified
  [PatientIntake] Step 2: PrescribeMedication child wf (PropagationScope.LINEAGE)
  [PrescribeMedication] Starting prescription: amoxicillin 500mg for bacterial sinusitis
  [PrescribeMedication] Step 1: CheckAllergies (no propagation)
  [CheckAllergies] Screening P-1042 for amoxicillin
  [PrescribeMedication] Step 1 complete: allergy clear
  [PrescribeMedication] Step 2: ScreenDrugInteractions (no propagation)
  [ScreenDrugInteractions] Screening amoxicillin 500mg for P-1042
  [PrescribeMedication] Step 2 complete: no interactions
  [PrescribeMedication] Step 3: ComplianceAudit child wf (PropagationScope.LINEAGE)
  [ComplianceAudit] Auditing prescription for patient P-1042
  [ComplianceAudit] Received propagated history with workflows: ['PatientIntake', 'PrescribeMedication']
  [ComplianceAudit] Verification:
    PatientIntake/VerifyInsurance:              completed=True
    PrescribeMedication/CheckAllergies:         completed=True
    PrescribeMedication/ScreenDrugInteractions: completed=True
  [ComplianceAudit] APPROVED (risk=0.10)
  [PrescribeMedication] Step 3 complete: compliance audit passed (risk=0.10, 2 workflow(s) verified)
  [PrescribeMedication] Step 4: DispenseMedication (PropagationScope.OWN_HISTORY)
  [DispenseMedication] Propagated workflows: ['PrescribeMedication']
  [DispenseMedication]   workflow: name=PrescribeMedication app=order-processor
  [DispenseMedication] DISPENSED: rx-P-1042-... (amoxicillin 500mg)
  [PrescribeMedication] Step 4 complete: dispensed (id=rx-P-1042-..., 1 workflow(s) verified)
  [PrescribeMedication] COMPLETE: dispensed: id=rx-P-1042-..., patient=P-1042, drug=amoxicillin 500mg
  [PatientIntake] COMPLETE: dispensed: id=rx-P-1042-..., patient=P-1042, drug=amoxicillin 500mg
  [main] Workflow completed! Output: "dispensed: ..."

================
= COMPLETE =
================
```

## Standalone-mode note

In standalone mode the sidecar will log `propagating unsigned workflow history to ...` warnings — these are expected. Without `WorkflowHistorySigning` enabled, propagated history chunks aren't cryptographically signed, which is fine for a local `dapr run` demo. Signing the chunks within an mTLS trust boundary is a production concern handled at the cluster/control-plane level and is out of scope for this quickstart.

## Stop the sample

```sh
dapr stop -f .
```

## References

- [Proposal: Workflow History Propagation (dapr/proposals#102)](https://github.com/dapr/proposals/issues/102)
- [Runtime PR: dapr/dapr#9810](https://github.com/dapr/dapr/pull/9810)
- [Python SDK PR: dapr/python-sdk#1025](https://github.com/dapr/python-sdk/pull/1025)
- [Canonical Go SDK reference: dapr/go-sdk#823](https://github.com/dapr/go-sdk/pull/823)
- [Sibling Go quickstart: dapr/quickstarts#1315](https://github.com/dapr/quickstarts/pull/1315)
- [Dapr Workflow documentation](https://docs.dapr.io/developing-applications/building-blocks/workflow/)
