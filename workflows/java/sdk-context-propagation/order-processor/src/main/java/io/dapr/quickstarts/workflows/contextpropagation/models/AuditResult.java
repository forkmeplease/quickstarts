package io.dapr.quickstarts.workflows.contextpropagation.models;

public class AuditResult {

  private boolean compliant;
  private double riskScore;
  private int reviewedWorkflows;
  private String notes;

  public AuditResult() {
  }

  public AuditResult(boolean compliant, double riskScore, int reviewedWorkflows, String notes) {
    this.compliant = compliant;
    this.riskScore = riskScore;
    this.reviewedWorkflows = reviewedWorkflows;
    this.notes = notes;
  }

  public boolean isCompliant() {
    return compliant;
  }

  public void setCompliant(boolean compliant) {
    this.compliant = compliant;
  }

  public double getRiskScore() {
    return riskScore;
  }

  public void setRiskScore(double riskScore) {
    this.riskScore = riskScore;
  }

  public int getReviewedWorkflows() {
    return reviewedWorkflows;
  }

  public void setReviewedWorkflows(int reviewedWorkflows) {
    this.reviewedWorkflows = reviewedWorkflows;
  }

  public String getNotes() {
    return notes;
  }

  public void setNotes(String notes) {
    this.notes = notes;
  }

  @Override
  public String toString() {
    return "AuditResult [compliant=" + compliant + ", riskScore=" + riskScore
        + ", reviewedWorkflows=" + reviewedWorkflows + ", notes=" + notes + "]";
  }
}
