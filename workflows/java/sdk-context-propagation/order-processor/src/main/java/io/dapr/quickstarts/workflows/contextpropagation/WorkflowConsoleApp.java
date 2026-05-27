package io.dapr.quickstarts.workflows.contextpropagation;

import io.dapr.quickstarts.workflows.contextpropagation.activities.CheckAllergiesActivity;
import io.dapr.quickstarts.workflows.contextpropagation.activities.DispenseMedicationActivity;
import io.dapr.quickstarts.workflows.contextpropagation.activities.ScreenDrugInteractionsActivity;
import io.dapr.quickstarts.workflows.contextpropagation.activities.VerifyInsuranceActivity;
import io.dapr.quickstarts.workflows.contextpropagation.models.PatientRecord;
import io.dapr.quickstarts.workflows.contextpropagation.workflows.ComplianceAuditWorkflow;
import io.dapr.quickstarts.workflows.contextpropagation.workflows.PatientIntakeWorkflow;
import io.dapr.quickstarts.workflows.contextpropagation.workflows.PrescribeMedicationWorkflow;
import io.dapr.workflows.client.DaprWorkflowClient;
import io.dapr.workflows.client.WorkflowInstanceStatus;
import io.dapr.workflows.runtime.WorkflowRuntime;
import io.dapr.workflows.runtime.WorkflowRuntimeBuilder;

import java.time.Duration;
import java.util.concurrent.TimeoutException;

public class WorkflowConsoleApp {

  public static void main(String[] args) throws Exception {
    System.out.println("================================================================");
    System.out.println("= WORKFLOW HISTORY PROPAGATION DEMO - PATIENT INTAKE (Java)    =");
    System.out.println("================================================================");
    System.out.println();
    System.out.println("  Flow: PatientIntake -> VerifyInsurance");
    System.out.println("           -> PrescribeMedication (child wf, LINEAGE)");
    System.out.println("               -> CheckAllergies -> ScreenDrugInteractions");
    System.out.println("               -> ComplianceAudit     (child wf, LINEAGE)     <-- sees PatientIntake + PrescribeMedication");
    System.out.println("               -> DispenseMedication  (activity, OWN_HISTORY) <-- sees only PrescribeMedication");
    System.out.println();

    // Wait for the sidecar to become available.
    Thread.sleep(5 * 1000);

    WorkflowRuntimeBuilder builder = new WorkflowRuntimeBuilder()
        .registerWorkflow(PatientIntakeWorkflow.class)
        .registerWorkflow(PrescribeMedicationWorkflow.class)
        .registerWorkflow(ComplianceAuditWorkflow.class);
    builder.registerActivity(VerifyInsuranceActivity.class);
    builder.registerActivity(CheckAllergiesActivity.class);
    builder.registerActivity(ScreenDrugInteractionsActivity.class);
    builder.registerActivity(DispenseMedicationActivity.class);

    WorkflowRuntime runtime = builder.build();
    System.out.println("Start workflow runtime");
    runtime.start(false);

    PatientRecord record = new PatientRecord(
        "P-1042", "Jane Doe", "bacterial sinusitis", "amoxicillin", 500);

    DaprWorkflowClient workflowClient = new DaprWorkflowClient();
    try (workflowClient) {
      String instanceId = workflowClient.scheduleNewWorkflow(PatientIntakeWorkflow.class, record);
      System.out.printf("Scheduled new workflow instance of PatientIntakeWorkflow with instance ID: %s%n",
          instanceId);

      try {
        workflowClient.waitForInstanceStart(instanceId, Duration.ofSeconds(10), false);
        System.out.printf("Workflow instance %s started%n", instanceId);
      } catch (TimeoutException e) {
        System.out.printf("Workflow instance %s did not start within 10 seconds%n", instanceId);
        return;
      }

      try {
        WorkflowInstanceStatus status = workflowClient.waitForInstanceCompletion(
            instanceId, Duration.ofSeconds(60), true);
        if (status != null) {
          System.out.printf("Workflow instance completed, out is: %s%n",
              status.getSerializedOutput());
        } else {
          System.out.printf("Workflow instance %s not found%n", instanceId);
        }
      } catch (TimeoutException e) {
        System.out.printf("Workflow instance %s did not complete within 60 seconds%n", instanceId);
      }
    }

    System.out.println();
    System.out.println("================================================================");
    System.out.println("=                          COMPLETE                            =");
    System.out.println("================================================================");
  }
}
