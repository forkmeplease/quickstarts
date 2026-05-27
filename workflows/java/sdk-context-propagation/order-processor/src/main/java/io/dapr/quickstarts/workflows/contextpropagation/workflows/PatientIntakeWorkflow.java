package io.dapr.quickstarts.workflows.contextpropagation.workflows;

import io.dapr.quickstarts.workflows.contextpropagation.activities.VerifyInsuranceActivity;
import io.dapr.quickstarts.workflows.contextpropagation.models.InsuranceResult;
import io.dapr.quickstarts.workflows.contextpropagation.models.PatientRecord;
import io.dapr.quickstarts.workflows.contextpropagation.models.PrescriptionResult;
import io.dapr.workflows.Workflow;
import io.dapr.workflows.WorkflowStub;
import io.dapr.workflows.WorkflowTaskOptions;
import org.slf4j.Logger;

/**
 * Root workflow. Verifies insurance, then invokes PrescribeMedicationWorkflow
 * with {@code WorkflowTaskOptions.propagateLineage()} so the child sees this
 * workflow's events (and will forward them further as part of its own
 * lineage propagation downstream).
 */
public class PatientIntakeWorkflow implements Workflow {
  @Override
  public WorkflowStub create() {
    return ctx -> {
      Logger logger = ctx.getLogger();
      PatientRecord rec = ctx.getInput(PatientRecord.class);
      logger.info("Starting intake for patient {}", rec.getPatientId());

      // Root workflow has no caller, so no propagated history is expected.
      ctx.getPropagatedHistory().ifPresentOrElse(
          h -> logger.warn("Unexpected propagated history at root: scope={}", h.getScope()),
          () -> logger.info("PROPAGATION-DEMO: root workflow received no propagated history (expected)"));

      // Step 1: VerifyInsurance (no propagation).
      InsuranceResult insurance = ctx.callActivity(
          VerifyInsuranceActivity.class.getName(), rec, InsuranceResult.class).await();
      if (!insurance.isApproved()) {
        logger.warn("Insurance verification failed for patient {}", rec.getPatientId());
        ctx.complete(new PrescriptionResult(false, null, rec.getPatientId(), rec.getMedication()));
        return;
      }
      logger.info("Insurance verified: policy {}", insurance.getPolicyNumber());

      // Step 2: PrescribeMedication child workflow with LINEAGE - the child
      // (and any grandchild it invokes with lineage) sees this workflow's
      // VerifyInsurance event as part of the ancestor chain.
      PrescriptionResult result = ctx.callChildWorkflow(
          PrescribeMedicationWorkflow.class.getName(),
          rec,
          null,
          WorkflowTaskOptions.propagateLineage(),
          PrescriptionResult.class).await();

      logger.info("Prescription pipeline complete: {}", result);
      ctx.complete(result);
    };
  }
}
