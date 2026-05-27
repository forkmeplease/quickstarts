package io.dapr.quickstarts.workflows.contextpropagation.activities;

import io.dapr.quickstarts.workflows.contextpropagation.models.PatientRecord;
import io.dapr.workflows.WorkflowActivity;
import io.dapr.workflows.WorkflowActivityContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class CheckAllergiesActivity implements WorkflowActivity {
  private static final Logger logger = LoggerFactory.getLogger(CheckAllergiesActivity.class);

  @Override
  public Object run(WorkflowActivityContext ctx) {
    PatientRecord rec = ctx.getInput(PatientRecord.class);
    logger.info("Screening {} for {} allergies", rec.getPatientId(), rec.getMedication());
    return true;
  }
}
