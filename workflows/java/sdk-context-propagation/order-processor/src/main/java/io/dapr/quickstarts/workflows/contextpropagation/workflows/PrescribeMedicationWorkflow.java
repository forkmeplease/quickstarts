package io.dapr.quickstarts.workflows.contextpropagation.workflows;

import io.dapr.durabletask.HistoryPropagationScope;
import io.dapr.durabletask.PropagatedHistory;
import io.dapr.quickstarts.workflows.contextpropagation.activities.CheckAllergiesActivity;
import io.dapr.quickstarts.workflows.contextpropagation.activities.DispenseMedicationActivity;
import io.dapr.quickstarts.workflows.contextpropagation.activities.ScreenDrugInteractionsActivity;
import io.dapr.quickstarts.workflows.contextpropagation.models.AuditResult;
import io.dapr.quickstarts.workflows.contextpropagation.models.DispenseResult;
import io.dapr.quickstarts.workflows.contextpropagation.models.PatientRecord;
import io.dapr.quickstarts.workflows.contextpropagation.models.PrescriptionResult;
import io.dapr.workflows.Workflow;
import io.dapr.workflows.WorkflowStub;
import io.dapr.workflows.WorkflowTaskOptions;
import org.slf4j.Logger;

import java.util.Optional;

/**
 * Child workflow invoked by PatientIntakeWorkflow with
 * {@code WorkflowTaskOptions.propagateLineage()}. Runs allergy and interaction
 * screening, then calls:
 * <ul>
 *   <li>{@code ComplianceAuditWorkflow} with {@code propagateLineage()} -
 *       grandchild sees PatientIntake + PrescribeMedication events.</li>
 *   <li>{@code DispenseMedicationActivity} with {@code propagateOwnHistory()} -
 *       activity sees ONLY PrescribeMedication events (trust boundary).</li>
 * </ul>
 */
public class PrescribeMedicationWorkflow implements Workflow {
  @Override
  public WorkflowStub create() {
    return ctx -> {
      Logger logger = ctx.getLogger();
      PatientRecord rec = ctx.getInput(PatientRecord.class);
      logger.info("Starting prescription: {} {}mg for {}",
          rec.getMedication(), rec.getDosage(), rec.getCondition());

      Optional<PropagatedHistory> historyOpt = ctx.getPropagatedHistory();
      historyOpt.ifPresent(h -> {
        logger.info("PROPAGATION-DEMO: scope={} workflows={}",
            h.getScope(), h.getWorkflows().size());
        if (h.getScope() != HistoryPropagationScope.LINEAGE) {
          logger.warn("Expected LINEAGE from parent but got {}", h.getScope());
        }
      });

      // Step 1: CheckAllergies (no propagation).
      ctx.callActivity(CheckAllergiesActivity.class.getName(), rec, Boolean.class).await();

      // Step 2: ScreenDrugInteractions (no propagation).
      ctx.callActivity(ScreenDrugInteractionsActivity.class.getName(), rec, Boolean.class).await();

      // Step 3: ComplianceAudit child workflow with LINEAGE - the audit sees
      // both PatientIntake events (insurance) AND PrescribeMedication events
      // (allergies, interactions) so it can verify the full upstream chain.
      AuditResult audit = ctx.callChildWorkflow(
          ComplianceAuditWorkflow.class.getName(),
          rec,
          null,
          WorkflowTaskOptions.propagateLineage(),
          AuditResult.class).await();
      logger.info("Compliance audit returned: {}", audit);

      if (!audit.isCompliant()) {
        logger.warn("Audit blocked dispensing - aborting prescription");
        ctx.complete(new PrescriptionResult(false, null, rec.getPatientId(), rec.getMedication()));
        return;
      }

      // Step 4: DispenseMedication activity with OWN_HISTORY - the pharmacy
      // dispense system only sees this workflow's own events; the
      // PatientIntake ancestor chain is intentionally hidden.
      DispenseResult dispense = ctx.callActivity(
          DispenseMedicationActivity.class.getName(),
          rec,
          WorkflowTaskOptions.propagateOwnHistory(),
          DispenseResult.class).await();
      logger.info("Dispense returned: {}", dispense);

      ctx.complete(new PrescriptionResult(true, dispense.getDispenseId(),
          rec.getPatientId(), rec.getMedication()));
    };
  }
}
