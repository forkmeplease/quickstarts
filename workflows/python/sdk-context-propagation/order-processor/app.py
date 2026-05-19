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

Scenario: credit-card payment processing with fraud detection.

Flow:
    MerchantCheckout (root workflow)
      └─ ValidateMerchant  (activity, no propagation)
      └─ ProcessPayment    (child workflow, PropagationScope.LINEAGE)
            └─ ValidateCard         (activity, no propagation)
            └─ CheckSpendingLimits  (activity, no propagation)
            └─ FraudDetection       (child workflow, PropagationScope.LINEAGE)
            |      reads: MerchantCheckout/ValidateMerchant
            |             ProcessPayment/ValidateCard
            |             ProcessPayment/CheckSpendingLimits
            └─ SettlePayment        (activity, PropagationScope.OWN_HISTORY)
                   reads: ProcessPayment events only (no ancestor chain)

This requires Dapr 1.18+ (dapr/dapr#9810) and dapr-ext-workflow 1.18+
(dapr/python-sdk#1025). Against an older sidecar the propagation field is
silently dropped and ctx.get_propagated_history() returns None.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Optional

import dapr.ext.workflow as wf

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PaymentRequest:
    card_last4: str
    amount: float
    currency: str
    merchant_id: str
    description: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "PaymentRequest":
        return cls(**json.loads(data))


@dataclass
class FraudCheckResult:
    risk_score: float
    approved: bool
    reason: str
    event_count: int


@dataclass
class SettlementResult:
    transaction_id: str
    status: str
    event_count: int


# ---------------------------------------------------------------------------
# Workflow runtime
# ---------------------------------------------------------------------------

wfr = wf.WorkflowRuntime()


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

@wfr.activity(name='validate_merchant')
def validate_merchant(ctx: wf.WorkflowActivityContext, req_json: str) -> bool:
    req = PaymentRequest.from_json(req_json)
    print(f'  [ValidateMerchant] Validating merchant {req.merchant_id}', flush=True)
    return True


@wfr.activity(name='validate_card')
def validate_card(ctx: wf.WorkflowActivityContext, req_json: str) -> bool:
    req = PaymentRequest.from_json(req_json)
    # This activity receives no propagated history (called without propagation= param)
    history = ctx.get_propagated_history()
    print(
        f'  [ValidateCard] Validating card ****{req.card_last4} '
        f'(propagated history: {_describe_activity_history(history)})',
        flush=True,
    )
    return True


@wfr.activity(name='check_spending_limits')
def check_spending_limits(ctx: wf.WorkflowActivityContext, req_json: str) -> bool:
    req = PaymentRequest.from_json(req_json)
    history = ctx.get_propagated_history()
    print(
        f'  [CheckSpendingLimits] Checking {req.amount} {req.currency} '
        f'(propagated history: {_describe_activity_history(history)})',
        flush=True,
    )
    return req.amount <= 10000


@wfr.activity(name='settle_payment')
def settle_payment(ctx: wf.WorkflowActivityContext, req_json: str) -> str:
    """Receives PropagationScope.OWN_HISTORY from ProcessPayment — sees only
    the ProcessPayment workflow's events, not the MerchantCheckout ancestor."""
    req = PaymentRequest.from_json(req_json)
    history = ctx.get_propagated_history()

    event_count = 0
    if history is not None:
        workflows = history.get_workflows()
        event_count = sum(1 for _ in workflows)  # coarse count; use history.events for full count
        print(f'  [SettlePayment] Propagated workflows: {[w.name for w in workflows]}', flush=True)
        for wf_result in workflows:
            print(
                f'  [SettlePayment]   workflow: name={wf_result.name} app={wf_result.app_id}',
                flush=True,
            )
    else:
        print('  [SettlePayment] No propagated history received', flush=True)

    txn_id = f'txn-{req.merchant_id}-{int(time.time() * 1000)}'
    print(f'  [SettlePayment] SETTLED: {txn_id}', flush=True)
    return json.dumps(asdict(SettlementResult(
        transaction_id=txn_id,
        status='settled',
        event_count=event_count,
    )))


# ---------------------------------------------------------------------------
# Child workflows
# ---------------------------------------------------------------------------

@wfr.workflow(name='FraudDetection')
def fraud_detection(ctx: wf.DaprWorkflowContext, req_json: str):
    """Grandchild workflow that inspects the full ancestor chain.

    Receives PropagationScope.LINEAGE from ProcessPayment, so its
    get_propagated_history() contains events from both MerchantCheckout
    and ProcessPayment.
    """
    req = PaymentRequest.from_json(req_json)
    print(
        f'  [FraudDetection] Checking payment ****{req.card_last4} {req.amount} {req.currency}',
        flush=True,
    )

    history = ctx.get_propagated_history()
    if history is None:
        print(
            '  [FraudDetection] WARNING: no propagated history — sidecar may not support 1.18+',
            flush=True,
        )
        result = FraudCheckResult(
            risk_score=1.0,
            approved=False,
            reason='no execution history provided — cannot verify caller pipeline',
            event_count=0,
        )
        return json.dumps(asdict(result))

    workflows = history.get_workflows()
    print(
        f'  [FraudDetection] Received propagated history with workflows: '
        f'{[w.name for w in workflows]}',
        flush=True,
    )

    # Verify the ancestor chain includes the required steps.
    try:
        merchant_wf = history.get_workflow_by_name('MerchantCheckout')
    except wf.PropagationNotFoundError:
        return json.dumps(asdict(FraudCheckResult(
            risk_score=0.9,
            approved=False,
            reason='MerchantCheckout missing from propagated history',
            event_count=0,
        )))

    try:
        process_wf = history.get_workflow_by_name('ProcessPayment')
    except wf.PropagationNotFoundError:
        return json.dumps(asdict(FraudCheckResult(
            risk_score=0.9,
            approved=False,
            reason='ProcessPayment missing from propagated history',
            event_count=0,
        )))

    try:
        merchant_act = merchant_wf.get_activity_by_name('validate_merchant')
    except wf.PropagationNotFoundError:
        return json.dumps(asdict(FraudCheckResult(
            risk_score=0.85,
            approved=False,
            reason='validate_merchant not found in MerchantCheckout history',
            event_count=0,
        )))

    try:
        card_act = process_wf.get_activity_by_name('validate_card')
        spending_act = process_wf.get_activity_by_name('check_spending_limits')
    except wf.PropagationNotFoundError as exc:
        return json.dumps(asdict(FraudCheckResult(
            risk_score=0.85,
            approved=False,
            reason=f'required activity missing from ProcessPayment history: {exc}',
            event_count=0,
        )))

    print(
        f'  [FraudDetection] Verification:\n'
        f'    MerchantCheckout/validate_merchant: completed={merchant_act.completed}\n'
        f'    ProcessPayment/validate_card:        completed={card_act.completed}\n'
        f'    ProcessPayment/check_spending_limits: completed={spending_act.completed}',
        flush=True,
    )

    if not (merchant_act.completed and card_act.completed and spending_act.completed):
        return json.dumps(asdict(FraudCheckResult(
            risk_score=0.9,
            approved=False,
            reason='required upstream checks not completed in propagated history',
            event_count=len(workflows),
        )))

    risk_score = 0.3 if req.amount > 1000 else 0.1
    print(f'  [FraudDetection] APPROVED (risk={risk_score:.2f})', flush=True)
    return json.dumps(asdict(FraudCheckResult(
        risk_score=risk_score,
        approved=True,
        reason='all upstream checks verified in propagated history',
        event_count=len(workflows),
    )))


@wfr.workflow(name='ProcessPayment')
def process_payment(ctx: wf.DaprWorkflowContext, req_json: str):
    """Child workflow — orchestrates card validation, fraud check, and settlement.

    Receives PropagationScope.LINEAGE from MerchantCheckout, so it holds
    the full ancestor chain when calling its own children.
    """
    req = PaymentRequest.from_json(req_json)
    print(
        f'  [ProcessPayment] Starting payment ****{req.card_last4} '
        f'{req.amount} {req.currency}',
        flush=True,
    )

    # Step 1: Validate card (no propagation)
    print('  [ProcessPayment] Step 1: validate_card (no propagation)', flush=True)
    card_valid = yield ctx.call_activity(validate_card, input=req_json)
    if not card_valid:
        return 'payment declined: invalid card'
    print('  [ProcessPayment] Step 1 complete: card valid', flush=True)

    # Step 2: Check spending limits (no propagation)
    print('  [ProcessPayment] Step 2: check_spending_limits (no propagation)', flush=True)
    within_limits = yield ctx.call_activity(check_spending_limits, input=req_json)
    if not within_limits:
        return 'payment declined: spending limit exceeded'
    print('  [ProcessPayment] Step 2 complete: within limits', flush=True)

    # Step 3: Fraud detection child workflow with LINEAGE propagation.
    # The grandchild sees both MerchantCheckout AND ProcessPayment events.
    print(
        '  [ProcessPayment] Step 3: FraudDetection child wf '
        '(PropagationScope.LINEAGE)',
        flush=True,
    )
    fraud_json = yield ctx.call_child_workflow(
        fraud_detection,
        input=req_json,
        propagation=wf.PropagationScope.LINEAGE,
    )
    fraud_result = FraudCheckResult(**json.loads(fraud_json))
    if not fraud_result.approved:
        return (
            f'payment declined: fraud check failed '
            f'(risk={fraud_result.risk_score:.2f}, reason={fraud_result.reason})'
        )
    print(
        f'  [ProcessPayment] Step 3 complete: fraud check passed '
        f'(risk={fraud_result.risk_score:.2f})',
        flush=True,
    )

    # Step 4: Settle the payment with OWN_HISTORY propagation.
    # SettlePayment only sees ProcessPayment's own events, not MerchantCheckout.
    print(
        '  [ProcessPayment] Step 4: settle_payment (PropagationScope.OWN_HISTORY)',
        flush=True,
    )
    settlement_json = yield ctx.call_activity(
        settle_payment,
        input=req_json,
        propagation=wf.PropagationScope.OWN_HISTORY,
    )
    settlement = SettlementResult(**json.loads(settlement_json))
    print(
        f'  [ProcessPayment] Step 4 complete: settled (txn={settlement.transaction_id})',
        flush=True,
    )

    result = (
        f'payment settled: txn={settlement.transaction_id}, '
        f'card=****{req.card_last4}, amount={req.amount} {req.currency}'
    )
    print(f'  [ProcessPayment] COMPLETE: {result}', flush=True)
    return result


@wfr.workflow(name='MerchantCheckout')
def merchant_checkout(ctx: wf.DaprWorkflowContext, req_json: str):
    """Root workflow — validates the merchant then delegates payment to a child
    workflow with full LINEAGE propagation so the grandchild FraudDetection
    can inspect the complete ancestor chain.
    """
    req = PaymentRequest.from_json(req_json)
    print(
        f'  [MerchantCheckout] Starting checkout for merchant {req.merchant_id}',
        flush=True,
    )

    # Step 1: Validate merchant (no propagation — plain activity)
    print('  [MerchantCheckout] Step 1: validate_merchant (no propagation)', flush=True)
    yield ctx.call_activity(validate_merchant, input=req_json)
    print('  [MerchantCheckout] Step 1 complete: merchant valid', flush=True)

    # Step 2: Delegate to ProcessPayment with LINEAGE propagation.
    # ProcessPayment inherits this workflow's history plus any it received from above.
    print(
        '  [MerchantCheckout] Step 2: ProcessPayment child wf '
        '(PropagationScope.LINEAGE)',
        flush=True,
    )
    result = yield ctx.call_child_workflow(
        process_payment,
        input=req_json,
        propagation=wf.PropagationScope.LINEAGE,
    )

    print(f'  [MerchantCheckout] COMPLETE: {result}', flush=True)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _describe_activity_history(history: Optional[wf.PropagatedHistory]) -> str:
    if history is None:
        return 'none'
    workflows = history.get_workflows()
    return f'{len(workflows)} workflow(s)'


def _banner(msg: str) -> str:
    line = '=' * (len(msg) + 4)
    return f'{line}\n= {msg} =\n{line}'


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    wfr.start()

    req = PaymentRequest(
        card_last4='4242',
        amount=149.99,
        currency='USD',
        merchant_id='merchant-abc',
        description='Online purchase',
    )

    print(_banner('WORKFLOW HISTORY PROPAGATION DEMO'), flush=True)
    print(flush=True)
    print('  Flow: MerchantCheckout -> validate_merchant', flush=True)
    print('           -> ProcessPayment (child wf, LINEAGE)', flush=True)
    print('               -> validate_card -> check_spending_limits', flush=True)
    print('               -> FraudDetection (child wf, LINEAGE)    <-- sees MerchantCheckout + ProcessPayment events', flush=True)
    print('               -> settle_payment (activity, OWN_HISTORY) <-- sees only ProcessPayment events', flush=True)
    print(flush=True)

    wf_client = wf.DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(
        workflow=merchant_checkout,
        input=req.to_json(),
        instance_id='checkout-001',
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
