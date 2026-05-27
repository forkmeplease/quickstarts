package io.dapr.quickstarts.workflows.contextpropagation.activities;

import io.dapr.quickstarts.workflows.contextpropagation.models.PatientRecord;
import io.dapr.workflows.WorkflowActivity;
import io.dapr.workflows.WorkflowActivityContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class ScreenDrugInteractionsActivity implements WorkflowActivity {
  private static final Logger logger = LoggerFactory.getLogger(ScreenDrugInteractionsActivity.class);

  @Override
  public Object run(WorkflowActivityContext ctx) {
    PatientRecord rec = ctx.getInput(PatientRecord.class);
    logger.info("Screening drug interactions for {} {}mg in patient {}",
        rec.getMedication(), rec.getDosage(), rec.getPatientId());
    return true;
  }
}
