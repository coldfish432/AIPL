package com.aipl.platform.domain;

public class Run {
    private final String runId;
    private final String planId;
    private final String status;

    private Run(Builder builder) {
        this.runId = builder.runId;
        this.planId = builder.planId;
        this.status = builder.status;
    }

    public String getRunId() {
        return runId;
    }

    public String getPlanId() {
        return planId;
    }

    public String getStatus() {
        return status;
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String runId;
        private String planId;
        private String status;

        public Builder runId(String runId) {
            this.runId = runId;
            return this;
        }

        public Builder planId(String planId) {
            this.planId = planId;
            return this;
        }

        public Builder status(String status) {
            this.status = status;
            return this;
        }

        public Run build() {
            return new Run(this);
        }
    }
}
