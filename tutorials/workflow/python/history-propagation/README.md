# Dapr Workflow History Propagation — Patient Intake

This example demonstrates how Dapr workflows can propagate their execution
history to child workflows and activities, so downstream consumers can
inspect the full (or partial) execution context of their caller. See the
[Workflow history propagation](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-history-propagation/)
docs for the concept overview.

The scenario is a patient intake / e-prescribing pipeline: a compliance
audit and a pharmacy dispense step refuse to act unless they can see
proof — in the propagated history — that the required upstream checks
(insurance, allergies, drug interactions) actually ran.

This is the Python sibling of the canonical Go quickstart in
[`tutorials/workflow/go/history-propagation`](../../go/history-propagation),
itself based on [dapr/go-sdk#823](https://github.com/dapr/go-sdk/pull/823).
Python runtime support landed in
[dapr/python-sdk#1025](https://github.com/dapr/python-sdk/pull/1025).

## Workflow architecture

```
PatientIntake (workflow)
├── VerifyInsurance (activity, no propagation)
└── PrescribeMedication (child workflow, PropagationScope.LINEAGE)
    ├── CheckAllergies (activity, no propagation)
    ├── ScreenDrugInteractions (activity, no propagation)
    ├── ComplianceAudit (child workflow, PropagationScope.LINEAGE)
    │     → sees PatientIntake + PrescribeMedication events
    └── DispenseMedication (activity, PropagationScope.OWN_HISTORY)
          → sees PrescribeMedication events only
          → refuses to dispense if the screening lineage is missing
```

### Propagation scope

| Mode | What it sends | Use case |
|------|---------------|----------|
| `PropagationScope.LINEAGE` | Caller's own events + any ancestor events it received | Full chain-of-custody verification (compliance audits) |
| `PropagationScope.OWN_HISTORY` | Caller's own events only (no ancestor chain) | Trust boundary — downstream only sees the immediate caller (pharmacy dispense) |

### Key demonstration

- **ComplianceAudit** receives the full lineage via `PropagationScope.LINEAGE` —
  it verifies that `VerifyInsurance` ran in the grandparent workflow
  (PatientIntake), plus `CheckAllergies` and `ScreenDrugInteractions`
  ran in PrescribeMedication.

- **DispenseMedication** receives only PrescribeMedication's history via
  `PropagationScope.OWN_HISTORY`. The PatientIntake ancestral history is
  excluded — the pharmacy system doesn't need (or get to see) the upstream
  chain. Before dispensing, the pharmacy verifies that `CheckAllergies` and
  `ScreenDrugInteractions` completed in the propagated history.

### Scenarios

The demo runs two scenarios back-to-back to show both the happy path and
the pharmacy's safety check:

1. **Lineage forwarded → pharmacy dispenses.** `PrescribeMedication` calls
   `DispenseMedication` with `PropagationScope.OWN_HISTORY`. The pharmacy
   sees the completed allergy and interaction screens in the propagated
   history and fills the prescription.

2. **Lineage withheld → pharmacy refuses.** `PrescribeMedication` calls
   `DispenseMedication` **without** history propagation (simulating an
   upstream system that fails to forward its lineage). With no propagated
   history to prove the prescription was screened, the pharmacy refuses to
   dispense and returns a `refused` result explaining what was missing.

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
history = ctx.get_propagated_history()  # PropagatedHistory | None

if history is not None:
    intake_wf  = history.get_last_workflow_by_name('PatientIntake')
    insurance  = intake_wf.get_last_activity_by_name('VerifyInsurance')
    print(insurance.completed)  # bool
    print(insurance.output)     # JSON string
```

Key symbols exported from `dapr.ext.workflow`:

- `PropagationScope` — enum with `LINEAGE` and `OWN_HISTORY`
- `PropagatedHistory` — top-level history object; `.get_workflows()`,
  `.get_last_workflow_by_name(name)`, `.events`, `.scope`, `.get_app_ids()`
- `WorkflowResult` — per-workflow slice; `.get_last_activity_by_name(name)`
- `ActivityResult` — `.completed`, `.output`
- `PropagationNotFoundError` — raised when a named workflow/activity is
  not present in the history

> **Replay safety:** workflow code runs many times during durable
> execution. Guard side-effecting calls — including `print()` — with
> `if not ctx.is_replaying:` so they only fire on the live execution.

## Running this example

Requires Dapr `1.18.0+` (workflow history propagation),
`dapr-ext-workflow>=1.18.0rc0`, and `dapr>=1.18.0rc0`.

Install the Python dependencies:

<!-- STEP
name: Install dependencies
expected_stdout_lines:
  - "patient-intake deps OK"
output_match_mode: substring
background: false
timeout_seconds: 180
-->

```bash
pip3 install -r requirements.txt && echo "patient-intake deps OK"
```

<!-- END_STEP -->

Run the demo:

<!-- STEP
name: Run history-propagation demo
expected_stdout_lines:
  - "SCENARIO 1: lineage forwarded"
  - "[ComplianceAudit] APPROVED"
  - "[DispenseMedication] DISPENSED"
  - "SCENARIO 2: lineage withheld"
  - "[DispenseMedication] REFUSED"
  - "pharmacy refused to dispense"
  - "missing lineage: no propagated history received from prescriber"
output_match_mode: substring
background: false
timeout_seconds: 180
sleep: 15
-->

```bash
dapr run -f .
```

<!-- END_STEP -->

The app runs both scenarios once and exits on its own — no Ctrl+C needed.

In scenario 1 (lineage forwarded) you'll see the pharmacy dispense:

```
[ComplianceAudit] Received propagated history: 15 events (scope: LINEAGE)
[ComplianceAudit] APPROVED (risk=0.10)
[DispenseMedication] Dispense request: amoxicillin 500mg ... (propagated history: 12 events, scope=OWN_HISTORY)
[DispenseMedication] DISPENSED: rx-P-1042-...
```

In scenario 2 (lineage withheld) the pharmacy refuses:

```
[PrescribeMedication] Step 4: CallActivity(DispenseMedication)
                      -> NO history propagation (negative scenario)
[DispenseMedication] Dispense request: penicillin 500mg ... (propagated history: none)
[DispenseMedication] REFUSED — no propagated history; cannot verify screening for P-2087
[PrescribeMedication] Step 4 BLOCKED: pharmacy refused to dispense (missing lineage: no propagated history received from prescriber)
```

In standalone mode the sidecar will log
`propagating unsigned workflow history to ...` warnings — these are
expected. Without `WorkflowHistorySigning` enabled, propagated history
chunks aren't cryptographically signed, which is fine for a local
`dapr run` demo. Signing the chunks within an mTLS trust boundary is a
production concern handled at the cluster/control-plane level and is out
of scope for this quickstart.

## Files

```
history-propagation/
├── README.md          # this file
├── dapr.yaml          # `dapr run -f .` config (appID, resources, command)
├── makefile           # wires the example into `make validate`
├── app.py             # registry + worker setup, schedules both scenarios
├── models.py          # PatientRecord, ComplianceResult, DispenseResult
├── workflow.py        # workflow + activity definitions, history helpers
└── requirements.txt   # Python deps
```
