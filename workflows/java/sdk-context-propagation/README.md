# Dapr Workflow — Context Propagation (Java SDK)

This quickstart demonstrates **workflow history propagation**, a new feature in Dapr 1.18 that lets a parent workflow share its execution history with child workflows and activities. Downstream services can inspect that history to make trust-aware decisions — without any external state store or custom messaging.

> **Runtime requirement**: Dapr 1.18+ ([dapr/dapr#9810](https://github.com/dapr/dapr/pull/9810))
> **SDK requirement**: `io.dapr:dapr-sdk-workflows >= 1.18.0-rc-2` ([dapr/java-sdk#1739](https://github.com/dapr/java-sdk/pull/1739), backported in [dapr/java-sdk#1751](https://github.com/dapr/java-sdk/pull/1751))
> **Proposal**: [dapr/proposals#102](https://github.com/dapr/proposals/issues/102)

## What is workflow context propagation?

When a parent workflow calls a child workflow or activity it can optionally attach a tamper-evident snapshot of its own execution history. The receiver reads that snapshot via `ctx.getPropagatedHistory()` and queries it by workflow name and activity name — letting it verify that the correct upstream steps ran before it proceeds.

### Two propagation modes

| Mode | Constant | What the receiver sees |
|------|----------|----------------------|
| **Own history** | `HistoryPropagationScope.OWN_HISTORY` | Only the direct caller's events |
| **Lineage** | `HistoryPropagationScope.LINEAGE` | Caller's events **plus** any ancestor history the caller itself received |

## Scenario: Patient intake / e-prescribing

A compliance audit and a pharmacy dispense step refuse to act unless the propagated history proves the required upstream checks (insurance, allergies, drug interactions) actually ran.

```
PatientIntake (root)
  ├─ VerifyInsurance        (activity, no propagation)
  └─ PrescribeMedication    (child wf, LINEAGE)
        ├─ CheckAllergies          (activity, no propagation)
        ├─ ScreenDrugInteractions  (activity, no propagation)
        ├─ ComplianceAudit         (grandchild wf, LINEAGE)
        |      reads PatientIntake/VerifyInsurance
        |            PrescribeMedication/CheckAllergies
        |            PrescribeMedication/ScreenDrugInteractions
        └─ DispenseMedication      (activity, OWN_HISTORY)
               reads PrescribeMedication events only
```

`ComplianceAudit` uses `HistoryPropagationScope.LINEAGE` to see the **full ancestor chain** — it can verify both the insurance check (performed by the grandparent `PatientIntake`) and the allergy/interaction checks (performed by the parent `PrescribeMedication`) before approving the prescription.

`DispenseMedication` uses `HistoryPropagationScope.OWN_HISTORY` to see only the **direct caller's events** — a trust-boundary mode that limits visibility to what `PrescribeMedication` itself executed. The pharmacy dispense system doesn't need (or get to see) the upstream patient-intake chain.

This sample mirrors the canonical Go reference [dapr/go-sdk#823](https://github.com/dapr/go-sdk/pull/823) and the [Go quickstart](https://github.com/dapr/quickstarts/pull/1315).

## Java API surface

```java
import io.dapr.durabletask.ActivityResult;
import io.dapr.durabletask.HistoryPropagationScope;
import io.dapr.durabletask.PropagatedHistory;
import io.dapr.durabletask.WorkflowResult;
import io.dapr.workflows.WorkflowTaskOptions;

// Parent workflow — propagate LINEAGE when calling a child workflow
AuditResult audit = ctx.callChildWorkflow(
    ComplianceAuditWorkflow.class.getName(),
    rec,
    /* instanceId */ null,
    WorkflowTaskOptions.propagateLineage(),
    AuditResult.class).await();

// Parent workflow — propagate OWN_HISTORY when calling an activity
DispenseResult dispense = ctx.callActivity(
    DispenseMedicationActivity.class.getName(),
    rec,
    WorkflowTaskOptions.propagateOwnHistory(),
    DispenseResult.class).await();

// Child workflow (or activity) — read the propagated history
Optional<PropagatedHistory> historyOpt = ctx.getPropagatedHistory();
historyOpt.ifPresent(history -> {
    history.getScope();         // HistoryPropagationScope (LINEAGE | OWN_HISTORY)
    history.getWorkflows();     // List<WorkflowResult> — ancestor first, then own

    // Look up a specific ancestor by workflow name
    Optional<WorkflowResult> intake = history.getLastWorkflowByName(
        PatientIntakeWorkflow.class.getName());

    // Inspect a specific upstream activity within that segment
    intake.flatMap(wf -> wf.getLastActivityByName(VerifyInsuranceActivity.class.getName()))
          .map(ActivityResult::isCompleted);
});
```

Key types exported from the Java SDK:

- `io.dapr.durabletask.HistoryPropagationScope` — enum with `NONE`, `OWN_HISTORY`, `LINEAGE`
- `io.dapr.workflows.WorkflowTaskOptions` — call `propagateLineage()` / `propagateOwnHistory()` to get a preconfigured options object
- `io.dapr.durabletask.PropagatedHistory` — top-level history object; call `getScope()`, `getWorkflows()`, `getLastWorkflowByName(name)`, `getWorkflowsByName(name)`, `getAppIDs()`
- `io.dapr.durabletask.WorkflowResult` — per-workflow slice; call `getName()`, `getAppId()`, `getInstanceId()`, `getLastActivityByName(name)`, `getLastChildWorkflowByName(name)`, and their plural counterparts
- `io.dapr.durabletask.ActivityResult` / `ChildWorkflowResult` — has `isCompleted()`, `isFailed()`, `getOutput()`, `getError()`

> **Replay safety**: workflow code runs many times during durable execution. Use `ctx.getLogger()` from inside a workflow body for replay-safe logging (the SDK suppresses log lines on replays). Inside activities — which never replay — a standard `LoggerFactory.getLogger(...)` is fine.

## Prerequisites

- [Dapr CLI](https://docs.dapr.io/getting-started/install-dapr-cli/) 1.17+
- Dapr runtime 1.18+ initialized (`dapr init --runtime-version=1.18.0-rc.4` or later)
- JDK 17+
- Maven 3.8+

## Run the sample

1. Build the application:

<!-- STEP
name: Install Java dependencies
-->

```bash
cd ./order-processor
mvn clean install
cd ..
```

<!-- END_STEP -->

2. Run the workflow with Dapr:

<!-- STEP
name: Run order-processor service
expected_stdout_lines:
  - 'WORKFLOW HISTORY PROPAGATION DEMO - PATIENT INTAKE (Java)'
  - 'PROPAGATION-DEMO: root workflow received no propagated history (expected)'
  - 'PROPAGATION-DEMO: scope=LINEAGE workflows=1'
  - 'PROPAGATION-DEMO: scope=LINEAGE workflows=2'
  - 'APPROVED (risk=0.10, 2 workflow(s) verified)'
  - 'PROPAGATION-DEMO: scope=OWN_HISTORY workflows=1'
  - 'Workflow instance completed, out is: {"dispensed":true'
expected_stderr_lines:
output_match_mode: substring
background: true
sleep: 15
timeout_seconds: 180
-->

```bash
dapr run -f .
```

<!-- END_STEP -->

3. Stop the sample:

```bash
dapr stop -f .
```

## Expected output

```
================================================================
= WORKFLOW HISTORY PROPAGATION DEMO - PATIENT INTAKE (Java)    =
================================================================

  Flow: PatientIntake -> VerifyInsurance
           -> PrescribeMedication (child wf, LINEAGE)
               -> CheckAllergies -> ScreenDrugInteractions
               -> ComplianceAudit     (child wf, LINEAGE)     <-- sees PatientIntake + PrescribeMedication
               -> DispenseMedication  (activity, OWN_HISTORY) <-- sees only PrescribeMedication

Start workflow runtime
Scheduled new workflow instance of PatientIntakeWorkflow with instance ID: <uuid>
Workflow instance <uuid> started
[PatientIntakeWorkflow] Starting intake for patient P-1042
[PatientIntakeWorkflow] PROPAGATION-DEMO: root workflow received no propagated history (expected)
[VerifyInsuranceActivity] Checking insurance coverage for patient P-1042
[PrescribeMedicationWorkflow] Starting prescription: amoxicillin 500mg for bacterial sinusitis
[PrescribeMedicationWorkflow] PROPAGATION-DEMO: scope=LINEAGE workflows=1
[CheckAllergiesActivity] Screening P-1042 for amoxicillin allergies
[ScreenDrugInteractionsActivity] Screening drug interactions for amoxicillin 500mg in patient P-1042
[ComplianceAuditWorkflow] Auditing prescription for patient P-1042
[ComplianceAuditWorkflow] PROPAGATION-DEMO: scope=LINEAGE workflows=2
[ComplianceAuditWorkflow]   ancestor workflow: name=...PatientIntakeWorkflow app=order-processor instance=<uuid>
[ComplianceAuditWorkflow]   ancestor workflow: name=...PrescribeMedicationWorkflow app=order-processor instance=<uuid>
[ComplianceAuditWorkflow]   upstream activity VerifyInsurance: completed=true
[ComplianceAuditWorkflow]   upstream activity CheckAllergies: completed=true
[ComplianceAuditWorkflow]   upstream activity ScreenDrugInteractions: completed=true
[ComplianceAuditWorkflow] APPROVED (risk=0.10, 2 workflow(s) verified)
[DispenseMedicationActivity] PROPAGATION-DEMO: scope=OWN_HISTORY workflows=1
[DispenseMedicationActivity]   ancestor workflow: name=...PrescribeMedicationWorkflow app=order-processor instance=<uuid>
[DispenseMedicationActivity] DISPENSED: rx-P-1042-<ts> (amoxicillin 500mg) for patient P-1042
Workflow instance completed, out is: {"dispensed":true,"dispenseId":"rx-P-1042-<ts>","patientId":"P-1042","medication":"amoxicillin"}

================================================================
=                          COMPLETE                            =
================================================================
```

## How it works

1. `PatientIntakeWorkflow` is the root — it receives no propagated history (`ctx.getPropagatedHistory()` returns `Optional.empty()`).
2. It calls `VerifyInsuranceActivity` as a plain activity (no propagation), then invokes `PrescribeMedicationWorkflow` with `WorkflowTaskOptions.propagateLineage()`.
3. `PrescribeMedicationWorkflow` receives a `PropagatedHistory` with `scope=LINEAGE` containing one ancestor (`PatientIntakeWorkflow`).
4. It calls `CheckAllergiesActivity` and `ScreenDrugInteractionsActivity` as plain activities (no propagation), then invokes `ComplianceAuditWorkflow` with `propagateLineage()`.
5. `ComplianceAuditWorkflow` receives a `PropagatedHistory` with `scope=LINEAGE` containing **two** ancestors (`PatientIntakeWorkflow` and `PrescribeMedicationWorkflow`). It uses `getLastActivityByName(...)` to verify each required upstream activity ran to completion before approving.
6. After the audit, `PrescribeMedicationWorkflow` calls `DispenseMedicationActivity` with `WorkflowTaskOptions.propagateOwnHistory()`. The activity receives a `PropagatedHistory` with `scope=OWN_HISTORY` containing **only** the direct caller (`PrescribeMedicationWorkflow`) — the grandparent `PatientIntakeWorkflow` is intentionally not visible (trust boundary).

If the quickstart is run against a Dapr runtime older than 1.18, the propagation field is silently dropped — `ctx.getPropagatedHistory()` returns `Optional.empty()` everywhere and `ComplianceAuditWorkflow` correctly refuses to approve the prescription (`dispensed=false`).

## Standalone-mode note

In standalone mode the sidecar will log `propagating unsigned workflow history to ...` warnings — these are expected. Without `WorkflowHistorySigning` enabled, propagated history chunks aren't cryptographically signed, which is fine for a local `dapr run` demo. Signing the chunks within an mTLS trust boundary is a production concern handled at the cluster/control-plane level and is out of scope for this quickstart.

## References

- [Proposal: Workflow History Propagation (dapr/proposals#102)](https://github.com/dapr/proposals/issues/102)
- [Runtime PR: dapr/dapr#9810](https://github.com/dapr/dapr/pull/9810)
- [Java SDK PR: dapr/java-sdk#1739](https://github.com/dapr/java-sdk/pull/1739) (backport: [#1751](https://github.com/dapr/java-sdk/pull/1751))
- [Canonical Go SDK reference: dapr/go-sdk#823](https://github.com/dapr/go-sdk/pull/823)
- [Sibling Python quickstart: dapr/quickstarts#1309](https://github.com/dapr/quickstarts/pull/1309)
- [Sibling .NET quickstart: dapr/quickstarts#1310](https://github.com/dapr/quickstarts/pull/1310)
- [Sibling Go quickstart: dapr/quickstarts#1315](https://github.com/dapr/quickstarts/pull/1315)
- [Dapr Workflow documentation](https://docs.dapr.io/developing-applications/building-blocks/workflow/)
