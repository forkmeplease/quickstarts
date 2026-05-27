package io.dapr.quickstarts.workflows.contextpropagation.models;

public class InsuranceResult {

  private boolean approved;
  private String policyNumber;

  public InsuranceResult() {
  }

  public InsuranceResult(boolean approved, String policyNumber) {
    this.approved = approved;
    this.policyNumber = policyNumber;
  }

  public boolean isApproved() {
    return approved;
  }

  public void setApproved(boolean approved) {
    this.approved = approved;
  }

  public String getPolicyNumber() {
    return policyNumber;
  }

  public void setPolicyNumber(String policyNumber) {
    this.policyNumber = policyNumber;
  }

  @Override
  public String toString() {
    return "InsuranceResult [approved=" + approved + ", policyNumber=" + policyNumber + "]";
  }
}
