package io.dapr.quickstarts.workflows.contextpropagation.models;

public class PatientRecord {

  private String patientId;
  private String name;
  private String condition;
  private String medication;
  private int dosage;

  public PatientRecord() {
  }

  public PatientRecord(String patientId, String name, String condition, String medication, int dosage) {
    this.patientId = patientId;
    this.name = name;
    this.condition = condition;
    this.medication = medication;
    this.dosage = dosage;
  }

  public String getPatientId() {
    return patientId;
  }

  public void setPatientId(String patientId) {
    this.patientId = patientId;
  }

  public String getName() {
    return name;
  }

  public void setName(String name) {
    this.name = name;
  }

  public String getCondition() {
    return condition;
  }

  public void setCondition(String condition) {
    this.condition = condition;
  }

  public String getMedication() {
    return medication;
  }

  public void setMedication(String medication) {
    this.medication = medication;
  }

  public int getDosage() {
    return dosage;
  }

  public void setDosage(int dosage) {
    this.dosage = dosage;
  }

  @Override
  public String toString() {
    return "PatientRecord [patientId=" + patientId + ", name=" + name
        + ", condition=" + condition + ", medication=" + medication
        + ", dosage=" + dosage + "mg]";
  }
}
