package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.JobRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.service.JobService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
public class JobController {
    private final JobService jobs;
    private final ObjectMapper mapper = new ObjectMapper();

    public JobController(JobService jobs) {
        this.jobs = jobs;
    }

    @PostMapping("/jobs")
    public ApiResponse<JsonNode> createJob(@RequestBody JobRequest req) throws Exception {
        String jobId = jobs.enqueue(req.task, req.planId, req.workspace);
        String payload = String.format("{\"job_id\":\"%s\",\"status\":\"queued\"}", jobId);
        return ApiResponse.ok(mapper.readTree(payload));
    }

    @GetMapping("/jobs")
    public ApiResponse<List<JsonNode>> listJobs() throws Exception {
        return ApiResponse.ok(jobs.listJobs(mapper));
    }

    @PostMapping("/jobs/{jobId}/cancel")
    public ApiResponse<JsonNode> cancelJob(@PathVariable String jobId) throws Exception {
        jobs.cancel(jobId);
        String payload = String.format("{\"job_id\":\"%s\",\"status\":\"canceled\"}", jobId);
        return ApiResponse.ok(mapper.readTree(payload));
    }
}
