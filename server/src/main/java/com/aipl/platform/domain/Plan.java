package com.aipl.platform.domain;

public class Plan {
    private final String planId;

    private Plan(Builder builder) {
        this.planId = builder.planId;
    }

    public String getPlanId() {
        return planId;
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String planId;

        public Builder planId(String planId) {
            this.planId = planId;
            return this;
        }

        public Plan build() {
            return new Plan(this);
        }
    }
}
