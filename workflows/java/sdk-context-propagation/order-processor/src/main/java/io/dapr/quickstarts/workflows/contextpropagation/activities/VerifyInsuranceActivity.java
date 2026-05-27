package io.dapr.quickstarts.workflows.contextpropagation.activities;

import io.dapr.quickstarts.workflows.contextpropagation.models.InsuranceResult;
import io.dapr.quickstarts.workflows.contextpropagation.models.PatientRecord;
import io.dapr.workflows.WorkflowActivity;
import io.dapr.workflows.WorkflowActivityContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class VerifyInsuranceActivity implements WorkflowActivity {
  private static final Logger logger = LoggerFactory.getLogger(VerifyInsuranceActivity.class);

  @Override
  public Object run(WorkflowActivityContext ctx) {
    PatientRecord rec = ctx.getInput(PatientRecord.class);
    logger.info("Checking insurance coverage for patient {}", rec.getPatientId());
    return new InsuranceResult(true, "POL-" + rec.getPatientId());
  }
}
