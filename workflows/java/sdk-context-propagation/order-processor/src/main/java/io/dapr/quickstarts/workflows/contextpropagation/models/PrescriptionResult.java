package io.dapr.quickstarts.workflows.contextpropagation.models;

public class PrescriptionResult {

  private boolean dispensed;
  private String dispenseId;
  private String patientId;
  private String medication;

  public PrescriptionResult() {
  }

  public PrescriptionResult(boolean dispensed, String dispenseId, String patientId, String medication) {
    this.dispensed = dispensed;
    this.dispenseId = dispenseId;
    this.patientId = patientId;
    this.medication = medication;
  }

  public boolean isDispensed() {
    return dispensed;
  }

  public void setDispensed(boolean dispensed) {
    this.dispensed = dispensed;
  }

  public String getDispenseId() {
    return dispenseId;
  }

  public void setDispenseId(String dispenseId) {
    this.dispenseId = dispenseId;
  }

  public String getPatientId() {
    return patientId;
  }

  public void setPatientId(String patientId) {
    this.patientId = patientId;
  }

  public String getMedication() {
    return medication;
  }

  public void setMedication(String medication) {
    this.medication = medication;
  }

  @Override
  public String toString() {
    return "PrescriptionResult [dispensed=" + dispensed + ", dispenseId=" + dispenseId
        + ", patientId=" + patientId + ", medication=" + medication + "]";
  }
}
