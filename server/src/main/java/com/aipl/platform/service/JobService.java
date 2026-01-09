package com.aipl.platform.service;

import com.aipl.platform.engine.EngineClient;
import com.aipl.platform.repository.JobRepository;
import com.aipl.platform.repository.JobRepository.JobRecord;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.UUID;

@Component
public class JobService {
    private final EngineClient engine;
    private final int maxWorkers;
    private final JobRepository jobRepository;

    public JobService(EngineClient engine, JobRepository jobRepository, @Value("${app.maxWorkers:2}") int maxWorkers) {
        this.engine = engine;
        this.maxWorkers = Math.max(1, maxWorkers);
        this.jobRepository = jobRepository;
    }

    @PostConstruct
    public void startWorkers() {
        for (int i = 0; i < maxWorkers; i++) {
            Thread t = new Thread(this::workerLoop, "job-worker-" + i);
            t.setDaemon(true);
            t.start();
        }
    }

    public String enqueue(String task, String planId, String workspace) throws Exception {
        String jobId = "job_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        jobRepository.insertJob(jobId, task, planId, workspace, "queued");
        return jobId;
    }

    public List<JsonNode> listJobs(com.fasterxml.jackson.databind.ObjectMapper mapper) throws Exception {
        return jobRepository.listJobs(mapper);
    }

    public void cancel(String jobId) throws Exception {
        jobRepository.cancel(jobId);
    }

    private void workerLoop() {
        while (true) {
            try {
                JobRecord record = jobRepository.fetchNextQueued().orElse(null);
                if (record == null) {
                    Thread.sleep(1000);
                    continue;
                }
                jobRepository.markRunning(record.jobId);

                JsonNode res = engine.run(record.task, record.planId, record.workspace, "autopilot");
                JsonNode data = res.get("data");
                String runId = data != null && data.has("run_id") ? data.get("run_id").asText() : null;
                String status = data != null && data.has("status") ? data.get("status").asText() : null;

                jobRepository.updateCompletion(record.jobId, status != null ? status : "done", runId);
            } catch (Exception e) {
                // swallow to keep worker alive
                try { Thread.sleep(1000); } catch (InterruptedException ignored) {}
            }
        }
    }
}
