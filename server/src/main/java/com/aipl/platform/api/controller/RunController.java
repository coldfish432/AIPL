package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.RunRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.engine.EnginePaths;
import com.aipl.platform.repository.RunRepository;
import com.aipl.platform.service.RunService;
import com.fasterxml.jackson.databind.JsonNode;
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
    private final RunRepository store;
    private final EnginePaths paths;
    private final RunService runService;

    public RunController(RunRepository store, EnginePaths paths, RunService runService) {
        this.store = store;
        this.paths = paths;
        this.runService = runService;
    }

    @PostMapping("/runs")
    public ApiResponse<JsonNode> run(@RequestBody RunRequest req) throws Exception {
        return ApiResponse.ok(runService.run(req.task, req.planId, req.workspace));
    }

    @GetMapping("/runs")
    public ApiResponse<List<JsonNode>> listRuns() throws Exception {
        return ApiResponse.ok(runService.listRuns());
    }

    @GetMapping("/runs/{runId}")
    public ApiResponse<JsonNode> status(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        return ApiResponse.ok(runService.status(planId, runId));
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
                    JsonNode res = runService.events(planId, runId, cur, limit);
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
                        JsonNode status = runService.status(planId, runId);
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
        return ApiResponse.ok(runService.events(planId, runId, cursor, limit));
    }

    @GetMapping("/runs/{runId}/artifacts")
    public ApiResponse<JsonNode> artifacts(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        return ApiResponse.ok(runService.artifacts(planId, runId));
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
        return ApiResponse.ok(runService.cancel(planId, runId));
    }

    @PostMapping("/runs/{runId}/retry")
    public ApiResponse<JsonNode> retry(@PathVariable String runId,
                                       @RequestParam(required = false) String planId,
                                       @RequestParam(defaultValue = "false") boolean force,
                                       @RequestParam(defaultValue = "false") boolean retryDeps,
                                       @RequestParam(required = false) String retryIdSuffix,
                                       @RequestParam(defaultValue = "false") boolean reuseTaskId) throws Exception {
        return ApiResponse.ok(runService.retry(planId, runId, force, retryDeps, retryIdSuffix, reuseTaskId));
    }

}
