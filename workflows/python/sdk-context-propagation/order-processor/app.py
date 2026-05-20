# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Workflow history propagation quickstart (Python SDK).

Scenario: patient intake / e-prescribing pipeline. A compliance audit and a
pharmacy dispense step refuse to act unless the propagated history proves
the required upstream checks (insurance, allergies, drug interactions)
actually ran.

Flow:
    PatientIntake (root workflow)
      |- VerifyInsurance      (activity, no propagation)
      `- PrescribeMedication  (child workflow, PropagationScope.LINEAGE)
            |- CheckAllergies         (activity, no propagation)
            |- ScreenDrugInteractions (activity, no propagation)
            |- ComplianceAudit        (grandchild wf, PropagationScope.LINEAGE)
            |     reads: PatientIntake/VerifyInsurance
            |            PrescribeMedication/CheckAllergies
            |            PrescribeMedication/ScreenDrugInteractions
            `- DispenseMedication     (activity, PropagationScope.OWN_HISTORY)
                  reads: PrescribeMedication events only (no PatientIntake)

This requires Dapr 1.18+ (dapr/dapr#9810) and dapr-ext-workflow 1.18+
(dapr/python-sdk#1025). Against an older sidecar the propagation field is
silently dropped and ctx.get_propagated_history() returns None.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

import dapr.ext.workflow as wf

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PatientRecord:
    patient_id: str
    name: str
    dob: str
    mrn: str
    condition: str
    medication: str
    dosage: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "PatientRecord":
        return cls(**json.loads(data))


@dataclass
class ComplianceResult:
    compliant: bool
    risk_score: float
    reason: str
    event_count: int


@dataclass
class DispenseResult:
    dispense_id: str
    status: str
    event_count: int


# ---------------------------------------------------------------------------
# Workflow runtime
# ---------------------------------------------------------------------------

wfr = wf.WorkflowRuntime()


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

@wfr.activity(name='VerifyInsurance')
def verify_insurance(ctx: wf.WorkflowActivityContext, rec_json: str) -> bool:
    rec = PatientRecord.from_json(rec_json)
    print(f'  [VerifyInsurance] Checking coverage for patient {rec.patient_id}', flush=True)
    return True


@wfr.activity(name='CheckAllergies')
def check_allergies(ctx: wf.WorkflowActivityContext, rec_json: str) -> bool:
    rec = PatientRecord.from_json(rec_json)
    print(
        f'  [CheckAllergies] Screening {rec.patient_id} for {rec.medication}',
        flush=True,
    )
    return True


@wfr.activity(name='ScreenDrugInteractions')
def screen_drug_interactions(ctx: wf.WorkflowActivityContext, rec_json: str) -> bool:
    rec = PatientRecord.from_json(rec_json)
    print(
        f'  [ScreenDrugInteractions] Screening {rec.medication} {rec.dosage:.0f}mg for {rec.patient_id}',
        flush=True,
    )
    return True


@wfr.activity(name='DispenseMedication')
def dispense_medication(ctx: wf.WorkflowActivityContext, rec_json: str) -> str:
    """Receives PropagationScope.OWN_HISTORY from PrescribeMedication — sees only
    the PrescribeMedication workflow's events, not the PatientIntake ancestor.

    The pharmacy dispense system intentionally does not get to see the
    upstream patient-intake chain; it only needs proof that the prescribing
    workflow itself ran the right checks.
    """
    rec = PatientRecord.from_json(rec_json)
    history = ctx.get_propagated_history()

    event_count = 0
    if history is not None:
        workflows = history.get_workflows()
        event_count = len(workflows)
        print(
            f'  [DispenseMedication] Propagated workflows: {[w.name for w in workflows]}',
            flush=True,
        )
        for wf_result in workflows:
            print(
                f'  [DispenseMedication]   workflow: name={wf_result.name} app={wf_result.app_id}',
                flush=True,
            )
    else:
        print('  [DispenseMedication] No propagated history received', flush=True)

    dispense_id = f'rx-{rec.patient_id}-{int(time.time() * 1000)}'
    print(
        f'  [DispenseMedication] DISPENSED: {dispense_id} ({rec.medication} {rec.dosage:.0f}mg)',
        flush=True,
    )
    return json.dumps(asdict(DispenseResult(
        dispense_id=dispense_id,
        status='dispensed',
        event_count=event_count,
    )))


# ---------------------------------------------------------------------------
# Child workflows
# ---------------------------------------------------------------------------

@wfr.workflow(name='ComplianceAudit')
def compliance_audit(ctx: wf.DaprWorkflowContext, rec_json: str):
    """Grandchild workflow that inspects the full ancestor chain.

    Receives PropagationScope.LINEAGE from PrescribeMedication, so its
    get_propagated_history() contains events from both PatientIntake and
    PrescribeMedication. It refuses to approve dispensing unless the required
    upstream steps (insurance, allergies, drug interactions) are all present
    and completed in the propagated history.
    """
    rec = PatientRecord.from_json(rec_json)
    if not ctx.is_replaying:
        print(
            f'  [ComplianceAudit] Auditing prescription for patient {rec.patient_id}',
            flush=True,
        )

    history = ctx.get_propagated_history()
    if history is None:
        if not ctx.is_replaying:
            print(
                '  [ComplianceAudit] WARNING: no propagated history — sidecar may not support 1.18+',
                flush=True,
            )
            print(
                '  [ComplianceAudit] BLOCKED — cannot verify upstream pipeline without history',
                flush=True,
            )
        return json.dumps(asdict(ComplianceResult(
            compliant=False,
            risk_score=1.0,
            reason='no execution history provided — cannot verify caller pipeline',
            event_count=0,
        )))

    workflows = history.get_workflows()
    if not ctx.is_replaying:
        print(
            f'  [ComplianceAudit] Received propagated history with workflows: '
            f'{[w.name for w in workflows]}',
            flush=True,
        )

    # Verify the ancestor chain includes the required workflows.
    try:
        intake_wf = history.get_workflow_by_name('PatientIntake')
    except wf.PropagationNotFoundError:
        return json.dumps(asdict(ComplianceResult(
            compliant=False,
            risk_score=0.9,
            reason='PatientIntake missing from propagated history',
            event_count=len(workflows),
        )))

    try:
        prescribe_wf = history.get_workflow_by_name('PrescribeMedication')
    except wf.PropagationNotFoundError:
        return json.dumps(asdict(ComplianceResult(
            compliant=False,
            risk_score=0.9,
            reason='PrescribeMedication missing from propagated history',
            event_count=len(workflows),
        )))

    # Verify the required activity completions are recorded.
    try:
        insurance_act = intake_wf.get_activity_by_name('VerifyInsurance')
    except wf.PropagationNotFoundError:
        return json.dumps(asdict(ComplianceResult(
            compliant=False,
            risk_score=0.85,
            reason='VerifyInsurance not found in PatientIntake history',
            event_count=len(workflows),
        )))

    try:
        allergies_act = prescribe_wf.get_activity_by_name('CheckAllergies')
        interactions_act = prescribe_wf.get_activity_by_name('ScreenDrugInteractions')
    except wf.PropagationNotFoundError as exc:
        return json.dumps(asdict(ComplianceResult(
            compliant=False,
            risk_score=0.85,
            reason=f'required activity missing from PrescribeMedication history: {exc}',
            event_count=len(workflows),
        )))

    if not ctx.is_replaying:
        print('  [ComplianceAudit] Verification:', flush=True)
        print(
            f'    PatientIntake/VerifyInsurance:              completed={insurance_act.completed}',
            flush=True,
        )
        print(
            f'    PrescribeMedication/CheckAllergies:         completed={allergies_act.completed}',
            flush=True,
        )
        print(
            f'    PrescribeMedication/ScreenDrugInteractions: completed={interactions_act.completed}',
            flush=True,
        )

    if not (insurance_act.completed and allergies_act.completed and interactions_act.completed):
        if not ctx.is_replaying:
            print(
                '  [ComplianceAudit] BLOCKED — required upstream checks not completed',
                flush=True,
            )
        return json.dumps(asdict(ComplianceResult(
            compliant=False,
            risk_score=0.9,
            reason='required upstream checks not completed in propagated history',
            event_count=len(workflows),
        )))

    risk_score = 0.3 if rec.dosage > 1000 else 0.1
    if not ctx.is_replaying:
        print(f'  [ComplianceAudit] APPROVED (risk={risk_score:.2f})', flush=True)
    return json.dumps(asdict(ComplianceResult(
        compliant=True,
        risk_score=risk_score,
        reason='all upstream checks verified in propagated history',
        event_count=len(workflows),
    )))


@wfr.workflow(name='PrescribeMedication')
def prescribe_medication(ctx: wf.DaprWorkflowContext, rec_json: str):
    """Child workflow — orchestrates allergy + interaction screening, compliance
    audit, and dispensing.

    Receives PropagationScope.LINEAGE from PatientIntake, so it holds the full
    ancestor chain when calling its own children. Calls ComplianceAudit with
    LINEAGE (audit needs to see the grandparent) and DispenseMedication with
    OWN_HISTORY (pharmacy only sees the prescribing step, not the intake).
    """
    rec = PatientRecord.from_json(rec_json)
    if not ctx.is_replaying:
        print(
            f'  [PrescribeMedication] Starting prescription: {rec.medication} '
            f'{rec.dosage:.0f}mg for {rec.condition}',
            flush=True,
        )

    # Step 1: Allergy check (no propagation — plain activity)
    if not ctx.is_replaying:
        print(
            '  [PrescribeMedication] Step 1: CheckAllergies (no propagation)',
            flush=True,
        )
    allergy_clear = yield ctx.call_activity(check_allergies, input=rec_json)
    if not allergy_clear:
        return 'prescription declined: known allergy'
    if not ctx.is_replaying:
        print('  [PrescribeMedication] Step 1 complete: allergy clear', flush=True)

    # Step 2: Drug interaction screen (no propagation)
    if not ctx.is_replaying:
        print(
            '  [PrescribeMedication] Step 2: ScreenDrugInteractions (no propagation)',
            flush=True,
        )
    interactions_clear = yield ctx.call_activity(screen_drug_interactions, input=rec_json)
    if not interactions_clear:
        return 'prescription declined: drug interaction risk'
    if not ctx.is_replaying:
        print('  [PrescribeMedication] Step 2 complete: no interactions', flush=True)

    # Step 3: Compliance audit grandchild workflow with LINEAGE propagation.
    # The grandchild sees both PatientIntake AND PrescribeMedication events.
    if not ctx.is_replaying:
        print(
            '  [PrescribeMedication] Step 3: ComplianceAudit child wf '
            '(PropagationScope.LINEAGE)',
            flush=True,
        )
    audit_json = yield ctx.call_child_workflow(
        compliance_audit,
        input=rec_json,
        propagation=wf.PropagationScope.LINEAGE,
    )
    audit = ComplianceResult(**json.loads(audit_json))
    if not audit.compliant:
        return (
            f'prescription blocked: compliance audit failed '
            f'(risk={audit.risk_score:.2f}, reason={audit.reason})'
        )
    if not ctx.is_replaying:
        print(
            f'  [PrescribeMedication] Step 3 complete: compliance audit passed '
            f'(risk={audit.risk_score:.2f}, {audit.event_count} workflow(s) verified)',
            flush=True,
        )

    # Step 4: Dispense the medication with OWN_HISTORY propagation.
    # DispenseMedication only sees PrescribeMedication's events, not PatientIntake.
    if not ctx.is_replaying:
        print(
            '  [PrescribeMedication] Step 4: DispenseMedication '
            '(PropagationScope.OWN_HISTORY)',
            flush=True,
        )
    dispense_json = yield ctx.call_activity(
        dispense_medication,
        input=rec_json,
        propagation=wf.PropagationScope.OWN_HISTORY,
    )
    dispense = DispenseResult(**json.loads(dispense_json))
    if not ctx.is_replaying:
        print(
            f'  [PrescribeMedication] Step 4 complete: dispensed '
            f'(id={dispense.dispense_id}, {dispense.event_count} workflow(s) verified)',
            flush=True,
        )

    result = (
        f'dispensed: id={dispense.dispense_id}, patient={rec.patient_id}, '
        f'drug={rec.medication} {rec.dosage:.0f}mg'
    )
    if not ctx.is_replaying:
        print(f'  [PrescribeMedication] COMPLETE: {result}', flush=True)
    return result


@wfr.workflow(name='PatientIntake')
def patient_intake(ctx: wf.DaprWorkflowContext, rec_json: str):
    """Root workflow — verifies the patient's insurance then delegates the
    prescription to a child workflow with full LINEAGE propagation so the
    grandchild ComplianceAudit can inspect the complete ancestor chain.
    """
    rec = PatientRecord.from_json(rec_json)
    if not ctx.is_replaying:
        print(
            f'  [PatientIntake] Starting intake for patient {rec.patient_id}',
            flush=True,
        )

    # Step 1: Verify insurance (no propagation — plain activity)
    if not ctx.is_replaying:
        print(
            '  [PatientIntake] Step 1: VerifyInsurance (no propagation)',
            flush=True,
        )
    insured = yield ctx.call_activity(verify_insurance, input=rec_json)
    if not insured:
        return 'intake declined: insurance not on file'
    if not ctx.is_replaying:
        print('  [PatientIntake] Step 1 complete: insurance verified', flush=True)

    # Step 2: Delegate to PrescribeMedication with LINEAGE propagation.
    # PrescribeMedication inherits this workflow's history so its own
    # grandchild ComplianceAudit can verify the complete ancestor chain.
    if not ctx.is_replaying:
        print(
            '  [PatientIntake] Step 2: PrescribeMedication child wf '
            '(PropagationScope.LINEAGE)',
            flush=True,
        )
    result = yield ctx.call_child_workflow(
        prescribe_medication,
        input=rec_json,
        propagation=wf.PropagationScope.LINEAGE,
    )

    if not ctx.is_replaying:
        print(f'  [PatientIntake] COMPLETE: {result}', flush=True)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _banner(msg: str) -> str:
    line = '=' * (len(msg) + 4)
    return f'{line}\n= {msg} =\n{line}'


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    wfr.start()

    rec = PatientRecord(
        patient_id='P-1042',
        name='Jane Doe',
        dob='1985-06-12',
        mrn='MRN-77231',
        condition='bacterial sinusitis',
        medication='amoxicillin',
        dosage=500,
    )

    print(_banner('WORKFLOW HISTORY PROPAGATION DEMO — PATIENT INTAKE'), flush=True)
    print(flush=True)
    print('  Flow: PatientIntake -> VerifyInsurance', flush=True)
    print('           -> PrescribeMedication (child wf, LINEAGE)', flush=True)
    print('               -> CheckAllergies -> ScreenDrugInteractions', flush=True)
    print('               -> ComplianceAudit (child wf, LINEAGE)        <-- sees PatientIntake + PrescribeMedication events', flush=True)
    print('               -> DispenseMedication (activity, OWN_HISTORY) <-- sees only PrescribeMedication events', flush=True)
    print(flush=True)

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(
        workflow=patient_intake,
        input=rec.to_json(),
        instance_id='intake-001',
    )
    print(f'  [main] Started workflow instance: {instance_id}', flush=True)

    try:
        state = wf_client.wait_for_workflow_completion(
            instance_id=instance_id,
            timeout_in_seconds=30,
        )
        if state is None:
            print('  [main] Workflow not found!', flush=True)
        elif state.runtime_status.name == 'COMPLETED':
            print(
                f'  [main] Workflow completed! Output: {state.serialized_output}',
                flush=True,
            )
        else:
            print(
                f'  [main] Workflow ended with status: {state.runtime_status.name}',
                flush=True,
            )
    except TimeoutError:
        print('  [main] Workflow timed out!', flush=True)

    print(flush=True)
    print(_banner('COMPLETE'), flush=True)

    wfr.shutdown()
