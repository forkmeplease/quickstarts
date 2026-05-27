package io.dapr.quickstarts.workflows.contextpropagation.models;

public class DispenseResult {

  private String dispenseId;
  private String status;
  private int reviewedWorkflows;

  public DispenseResult() {
  }

  public DispenseResult(String dispenseId, String status, int reviewedWorkflows) {
    this.dispenseId = dispenseId;
    this.status = status;
    this.reviewedWorkflows = reviewedWorkflows;
  }

  public String getDispenseId() {
    return dispenseId;
  }

  public void setDispenseId(String dispenseId) {
    this.dispenseId = dispenseId;
  }

  public String getStatus() {
    return status;
  }

  public void setStatus(String status) {
    this.status = status;
  }

  public int getReviewedWorkflows() {
    return reviewedWorkflows;
  }

  public void setReviewedWorkflows(int reviewedWorkflows) {
    this.reviewedWorkflows = reviewedWorkflows;
  }

  @Override
  public String toString() {
    return "DispenseResult [dispenseId=" + dispenseId + ", status=" + status
        + ", reviewedWorkflows=" + reviewedWorkflows + "]";
  }
}
