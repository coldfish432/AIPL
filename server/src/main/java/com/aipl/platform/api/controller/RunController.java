package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.AssistantConfirmRequest;
import com.aipl.platform.api.dto.request.RunRequest;
import com.aipl.platform.api.dto.request.ReworkRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.engine.EnginePaths;
import com.aipl.platform.repository.RunRepository;
import com.aipl.platform.service.RunService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.awt.Desktop;
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
    private final ObjectMapper mapper = new ObjectMapper();

    public RunController(RunRepository store, EnginePaths paths, RunService runService) {
        this.store = store;
        this.paths = paths;
        this.runService = runService;
    }

    @PostMapping("/runs")
    public ApiResponse<JsonNode> run(@RequestBody RunRequest req) throws Exception {
        JsonNode res = runService.run(req.task, req.planId, req.workspace, req.mode, req.policy);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/assistant/confirm")
    public ApiResponse<JsonNode> assistantConfirm(@RequestBody AssistantConfirmRequest req) throws Exception {
        String mode = (req.mode == null || req.mode.isBlank()) ? "autopilot" : req.mode;
        String policy = (req.policy == null || req.policy.isBlank()) ? "guarded" : req.policy;
        JsonNode res = runService.runPlan(req.planId, req.workspace, mode, policy);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @GetMapping("/runs")
    public ApiResponse<List<JsonNode>> listRuns() throws Exception {
        return ApiResponse.ok(runService.listRuns());
    }

    @GetMapping("/runs/{runId}")
    public ApiResponse<JsonNode> status(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        JsonNode res = runService.status(planId, runId);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
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
                            try {
                                emitter.send(SseEmitter.event()
                                        .name("heartbeat")
                                        .data("{\"ts\":" + System.currentTimeMillis() + ",\"cursor\":" + cur + "}"));
                            } catch (Exception ignored) {
                                // ignore heartbeat failures
                            }
                        }
                    }
                    if (idle >= 5) {
                        JsonNode status = runService.status(planId, runId);
                        JsonNode sd = status.get("data");
                        if (sd != null) {
                            String st = sd.get("status").asText("running");
                            if ("done".equals(st) || "failed".equals(st) || "canceled".equals(st) || "awaiting_review".equals(st) || "discarded".equals(st)) {
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
        JsonNode res = runService.events(planId, runId, cursor, limit);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @GetMapping("/runs/{runId}/artifacts")
    public ApiResponse<JsonNode> artifacts(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        JsonNode res = runService.artifacts(planId, runId);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
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
        JsonNode res = runService.cancel(planId, runId);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/runs/{runId}/apply")
    public ApiResponse<JsonNode> apply(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        JsonNode res = runService.apply(planId, runId);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/runs/{runId}/discard")
    public ApiResponse<JsonNode> discard(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        JsonNode res = runService.discard(planId, runId);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/runs/{runId}/open-file")
    public ApiResponse<JsonNode> openFile(@PathVariable String runId,
                                          @RequestParam(required = false) String planId,
                                          @RequestBody(required = false) JsonNode payload) throws Exception {
        String relPath = payload != null && payload.has("path") ? payload.get("path").asText(null) : null;
        if (relPath == null || relPath.isBlank()) {
            return ApiResponse.fail("path is required");
        }
        String resolvedPlanId = (planId != null && !planId.isBlank()) ? planId : paths.resolvePlanIdForRun(runId);
        Path runDir = paths.resolveRunDir(resolvedPlanId, runId);
        if (runDir == null || !Files.exists(runDir)) {
            return ApiResponse.fail("run not found");
        }
        Path metaPath = runDir.resolve("meta.json");
        if (!Files.exists(metaPath)) {
            return ApiResponse.fail("meta not found");
        }
        JsonNode meta = mapper.readTree(metaPath.toFile());
        String stageRoot = meta.path("workspace_stage_root").asText(null);
        String mainRoot = meta.path("workspace_main_root").asText(null);
        if ((stageRoot == null || stageRoot.isBlank()) && (mainRoot == null || mainRoot.isBlank())) {
            return ApiResponse.fail("workspace root not found");
        }
        Path target = resolveWorkspacePath(stageRoot, relPath);
        if (target == null) {
            target = resolveWorkspacePath(mainRoot, relPath);
        }
        if (target == null) {
            return ApiResponse.fail("file not found");
        }
        openPath(target);
        ObjectNode res = mapper.createObjectNode();
        res.put("opened", true);
        res.put("path", target.toString());
        return ApiResponse.ok(res);
    }


    @PostMapping("/runs/{runId}/rework")
    public ApiResponse<JsonNode> rework(@PathVariable String runId, @RequestParam(required = false) String planId, @RequestBody ReworkRequest req) throws Exception {
        JsonNode res = runService.rework(planId, runId, req.stepId, req.feedback, req.scope);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/runs/{runId}/retry")
    public ApiResponse<JsonNode> retry(@PathVariable String runId,
                                       @RequestParam(required = false) String planId,
                                       @RequestParam(defaultValue = "false") boolean force,
                                       @RequestParam(defaultValue = "false") boolean retryDeps,
                                       @RequestParam(required = false) String retryIdSuffix,
                                       @RequestParam(defaultValue = "false") boolean reuseTaskId) throws Exception {
        JsonNode res = runService.retry(planId, runId, force, retryDeps, retryIdSuffix, reuseTaskId);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @DeleteMapping("/runs/{runId}")
    public ApiResponse<JsonNode> deleteRun(@PathVariable String runId, @RequestParam(required = false) String planId) throws Exception {
        return ApiResponse.ok(runService.deleteRun(planId, runId));
    }

    private void openPath(Path target) throws Exception {
        String os = System.getProperty("os.name", "").toLowerCase();
        if (os.contains("win")) {
            new ProcessBuilder("explorer", "/select,", target.toString()).start();
            return;
        }
        if (os.contains("mac")) {
            new ProcessBuilder("open", "-R", target.toString()).start();
            return;
        }
        Path folder = target.getParent();
        if (folder == null) {
            folder = target;
        }
        if (Desktop.isDesktopSupported()) {
            Desktop desktop = Desktop.getDesktop();
            if (desktop.isSupported(Desktop.Action.OPEN)) {
                desktop.open(folder.toFile());
                return;
            }
        }
        new ProcessBuilder("xdg-open", folder.toString()).start();
    }

    private Path resolveWorkspacePath(String workspaceRoot, String relPath) {
        if (workspaceRoot == null || workspaceRoot.isBlank()) {
            return null;
        }
        Path base = Path.of(workspaceRoot).toAbsolutePath().normalize();
        Path rel = Path.of(relPath);
        if (rel.isAbsolute()) {
            return null;
        }
        Path target = base.resolve(rel).normalize();
        if (!target.startsWith(base)) {
            return null;
        }
        if (!Files.exists(target)) {
            return null;
        }
        return target;
    }

}
