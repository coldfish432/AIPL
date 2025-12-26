package com.aipl.platform.domain;

public class Job {
    private final String jobId;
    private final String task;
    private final String workspace;

    private Job(Builder builder) {
        this.jobId = builder.jobId;
        this.task = builder.task;
        this.workspace = builder.workspace;
    }

    public String getJobId() {
        return jobId;
    }

    public String getTask() {
        return task;
    }

    public String getWorkspace() {
        return workspace;
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String jobId;
        private String task;
        private String workspace;

        public Builder jobId(String jobId) {
            this.jobId = jobId;
            return this;
        }

        public Builder task(String task) {
            this.task = task;
            return this;
        }

        public Builder workspace(String workspace) {
            this.workspace = workspace;
            return this;
        }

        public Job build() {
            return new Job(this);
        }
    }
}
