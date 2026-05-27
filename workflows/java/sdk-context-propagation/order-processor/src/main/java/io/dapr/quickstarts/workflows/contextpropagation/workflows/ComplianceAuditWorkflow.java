package io.dapr.quickstarts.workflows.contextpropagation.workflows;

import io.dapr.durabletask.ActivityResult;
import io.dapr.durabletask.HistoryPropagationScope;
import io.dapr.durabletask.PropagatedHistory;
import io.dapr.durabletask.WorkflowResult;
import io.dapr.quickstarts.workflows.contextpropagation.activities.CheckAllergiesActivity;
import io.dapr.quickstarts.workflows.contextpropagation.activities.ScreenDrugInteractionsActivity;
import io.dapr.quickstarts.workflows.contextpropagation.activities.VerifyInsuranceActivity;
import io.dapr.quickstarts.workflows.contextpropagation.models.AuditResult;
import io.dapr.quickstarts.workflows.contextpropagation.models.PatientRecord;
import io.dapr.workflows.Workflow;
import io.dapr.workflows.WorkflowStub;
import org.slf4j.Logger;

import java.util.Optional;

/**
 * Grandchild workflow invoked by PrescribeMedicationWorkflow with
 * {@code WorkflowTaskOptions.propagateLineage()}. Sees the full ancestor chain
 * (PatientIntake + PrescribeMedication) and verifies that the required
 * upstream activities (insurance, allergies, drug interactions) actually ran
 * before approving the prescription.
 */
public class ComplianceAuditWorkflow implements Workflow {
  @Override
  public WorkflowStub create() {
    return ctx -> {
      Logger logger = ctx.getLogger();
      PatientRecord rec = ctx.getInput(PatientRecord.class);
      logger.info("Auditing prescription for patient {}", rec.getPatientId());

      Optional<PropagatedHistory> historyOpt = ctx.getPropagatedHistory();
      if (historyOpt.isEmpty()) {
        logger.warn("No propagated history received - cannot verify caller pipeline");
        ctx.complete(new AuditResult(false, 1.0, 0,
            "no execution history provided - cannot verify caller pipeline"));
        return;
      }

      PropagatedHistory history = historyOpt.get();
      int reviewedWorkflows = history.getWorkflows().size();
      logger.info("PROPAGATION-DEMO: scope={} workflows={}",
          history.getScope(), reviewedWorkflows);
      for (WorkflowResult wf : history.getWorkflows()) {
        logger.info("  ancestor workflow: name={} app={} instance={}",
            wf.getName(), wf.getAppId(), wf.getInstanceId());
      }

      if (history.getScope() != HistoryPropagationScope.LINEAGE) {
        logger.warn("Expected LINEAGE but got {}", history.getScope());
      }

      // Verify the grandparent ran insurance verification.
      Optional<WorkflowResult> intakeOpt = history.getLastWorkflowByName(
          PatientIntakeWorkflow.class.getName());
      boolean insuranceVerified = intakeOpt
          .flatMap(wf -> wf.getLastActivityByName(VerifyInsuranceActivity.class.getName()))
          .map(ActivityResult::isCompleted)
          .orElse(false);

      // Verify the direct parent ran allergy and interaction checks.
      Optional<WorkflowResult> parentOpt = history.getLastWorkflowByName(
          PrescribeMedicationWorkflow.class.getName());
      boolean allergiesChecked = parentOpt
          .flatMap(wf -> wf.getLastActivityByName(CheckAllergiesActivity.class.getName()))
          .map(ActivityResult::isCompleted)
          .orElse(false);
      boolean interactionsScreened = parentOpt
          .flatMap(wf -> wf.getLastActivityByName(ScreenDrugInteractionsActivity.class.getName()))
          .map(ActivityResult::isCompleted)
          .orElse(false);

      logger.info("  upstream activity VerifyInsurance: completed={}", insuranceVerified);
      logger.info("  upstream activity CheckAllergies: completed={}", allergiesChecked);
      logger.info("  upstream activity ScreenDrugInteractions: completed={}", interactionsScreened);

      boolean compliant = insuranceVerified && allergiesChecked && interactionsScreened;
      if (compliant) {
        logger.info("APPROVED (risk=0.10, {} workflow(s) verified)", reviewedWorkflows);
        ctx.complete(new AuditResult(true, 0.10, reviewedWorkflows,
            "all upstream checks verified"));
      } else {
        logger.warn("BLOCKED - missing upstream checks: insurance={} allergies={} interactions={}",
            insuranceVerified, allergiesChecked, interactionsScreened);
        ctx.complete(new AuditResult(false, 0.9, reviewedWorkflows,
            "missing one or more required upstream checks"));
      }
    };
  }
}
