package io.dapr.quickstarts.workflows.contextpropagation.activities;

import io.dapr.durabletask.ActivityResult;
import io.dapr.durabletask.HistoryPropagationScope;
import io.dapr.durabletask.PropagatedHistory;
import io.dapr.durabletask.WorkflowResult;
import io.dapr.quickstarts.workflows.contextpropagation.models.DispenseResult;
import io.dapr.quickstarts.workflows.contextpropagation.models.PatientRecord;
import io.dapr.workflows.WorkflowActivity;
import io.dapr.workflows.WorkflowActivityContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Optional;

public class DispenseMedicationActivity implements WorkflowActivity {
  private static final Logger logger = LoggerFactory.getLogger(DispenseMedicationActivity.class);

  @Override
  public Object run(WorkflowActivityContext ctx) {
    PatientRecord rec = ctx.getInput(PatientRecord.class);

    // The parent (PrescribeMedicationWorkflow) invoked this activity with
    // WorkflowTaskOptions.propagateOwnHistory(), so the activity sees ONLY the
    // direct caller's events — the upstream PatientIntakeWorkflow chain is
    // intentionally hidden (trust boundary).
    Optional<PropagatedHistory> historyOpt = ctx.getPropagatedHistory();
    int reviewedWorkflows = 0;
    if (historyOpt.isPresent()) {
      PropagatedHistory history = historyOpt.get();
      reviewedWorkflows = history.getWorkflows().size();
      logger.info("PROPAGATION-DEMO: scope={} workflows={}",
          history.getScope(), reviewedWorkflows);
      for (WorkflowResult wf : history.getWorkflows()) {
        logger.info("  ancestor workflow: name={} app={} instance={}",
            wf.getName(), wf.getAppId(), wf.getInstanceId());
        // Show how to look up specific upstream activities by name within the
        // propagated workflow segment.
        Optional<ActivityResult> allergyCheck = wf.getLastActivityByName(
            "io.dapr.quickstarts.workflows.contextpropagation.activities.CheckAllergiesActivity");
        allergyCheck.ifPresent(a -> logger.info(
            "  upstream activity CheckAllergiesActivity: completed={} failed={}",
            a.isCompleted(), a.isFailed()));
      }
      if (history.getScope() != HistoryPropagationScope.OWN_HISTORY) {
        logger.warn("Expected OWN_HISTORY but got {}", history.getScope());
      }
    } else {
      logger.info("No propagated history received - dispense activity invoked without propagation");
    }

    String dispenseId = "rx-" + rec.getPatientId() + "-" + System.currentTimeMillis();
    logger.info("DISPENSED: {} ({} {}mg) for patient {}",
        dispenseId, rec.getMedication(), rec.getDosage(), rec.getPatientId());

    return new DispenseResult(dispenseId, "dispensed", reviewedWorkflows);
  }
}
