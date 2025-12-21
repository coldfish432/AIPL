package com.aipl.platform.api;

import com.aipl.platform.engine.EngineClient;
import com.aipl.platform.engine.EnginePaths;
import com.aipl.platform.store.RunStore;
import com.aipl.platform.store.JobService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
@RequestMapping("/api")
public class RunController {
    private final EngineClient engine;
    private final RunStore store;
    private final EnginePaths paths;
    private final JobService jobs;
    private final ObjectMapper mapper = new ObjectMapper();

    public RunController(EngineClient engine, RunStore store, EnginePaths paths, JobService jobs) {
        this.engine = engine;
        this.store = store;
        this.paths = paths;
        this.jobs = jobs;
    }

    @PostMapping("/plans")
    public ApiResponse<JsonNode> plan(@RequestBody PlanRequest req) throws Exception {
        JsonNode res = engine.plan(req.goal, req.planId, req.workspace);
        store.upsertPlan(res);
        return ApiResponse.ok(res);
    }

    @PostMapping("/runs")
    public ApiResponse<JsonNode> run(@RequestBody RunRequest req) throws Exception {
        JsonNode res = engine.run(req.goal, req.planId, req.workspace);
        store.upsertRun(res);
        return ApiResponse.ok(res);
    }

    @GetMapping("/runs/{runId}")
    public ApiResponse<JsonNode> status(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        JsonNode res = engine.status(planId, runId);
        store.upsertRun(res);
        return ApiResponse.ok(res);
    }

    
    @GetMapping("/runs/{runId}/events/stream")
    public SseEmitter stream(@PathVariable String runId, @RequestParam(required = false) String planId,
                             @RequestParam(required = false) Integer cursor,
                             @RequestParam(defaultValue = "200") int limit) throws Exception {
        SseEmitter emitter = new SseEmitter(0L);
        int start = cursor != null ? cursor : store.getCursor(runId);
        new Thread(() -> {
            int cur = start;
            int idle = 0;
            try {
                while (true) {
                    JsonNode res = engine.events(planId, runId, cur, limit);
                    JsonNode data = res.get("data");
                    if (data != null) {
                        emitter.send(ApiResponse.ok(data));
                        int next = data.get("next_cursor").asInt(cur);
                        if (next != cur) {
                            cur = next;
                            store.setCursor(runId, cur);
                            idle = 0;
                        } else {
                            idle++;
                        }
                    }
                    if (idle >= 5) {
                        JsonNode status = engine.status(planId, runId);
                        JsonNode sd = status.get("data");
                        if (sd != null) {
                            String st = sd.get("status").asText("running");
                            if ("done".equals(st) || "failed".equals(st) || "canceled".equals(st)) {
                                emitter.complete();
                                break;
                            }
                        }
                    }
                    Thread.sleep(1000);
                }
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        }).start();
        return emitter;
    }

    @GetMapping("/runs/{runId}/events")
    public ApiResponse<JsonNode> events(@PathVariable String runId, @RequestParam(required = false) String planId,
                           @RequestParam(defaultValue = "0") int cursor,
                           @RequestParam(defaultValue = "200") int limit) throws Exception {
        return ApiResponse.ok(engine.events(planId, runId, cursor, limit));
    }

    @GetMapping("/runs/{runId}/artifacts")
    public ApiResponse<JsonNode> artifacts(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        return ApiResponse.ok(engine.artifacts(planId, runId));
    }

    
    @PostMapping("/jobs")
    public ApiResponse<JsonNode> createJob(@RequestBody JobRequest req) throws Exception {
        String jobId = jobs.enqueue(req.goal, req.planId, req.workspace);
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

    
    @GetMapping("/runs/{runId}/artifacts/download")
    public ResponseEntity<byte[]> download(@PathVariable String runId, @RequestParam String path, @RequestParam(required = false) String planId) throws Exception {
        Path runDir = paths.resolveRunDir(planId, runId);
        if (runDir == null) {
            return ResponseEntity.notFound().build();
        }
        Path target = runDir.resolve(path).normalize();
        if (!target.startsWith(runDir)) {
            return ResponseEntity.badRequest().build();
        }
        if (!Files.exists(target) || Files.isDirectory(target)) {
            return ResponseEntity.notFound().build();
        }
        byte[] bytes = Files.readAllBytes(target);
        return ResponseEntity.ok().header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + target.getFileName() + "\"").body(bytes);
    }

    @PostMapping("/runs/{runId}/cancel")
    public ApiResponse<JsonNode> cancel(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        JsonNode res = engine.cancel(planId, runId);
        store.upsertRun(res);
        return ApiResponse.ok(res);
    }
}
