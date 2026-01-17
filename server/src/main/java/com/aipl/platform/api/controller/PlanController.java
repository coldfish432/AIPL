package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.AssistantChatRequest;
import com.aipl.platform.api.dto.request.AssistantPlanRequest;
import com.aipl.platform.api.dto.request.PlanRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.engine.EngineCommandBuilder;
import com.aipl.platform.engine.EnginePaths;
import com.aipl.platform.service.AssistantService;
import com.aipl.platform.service.PlanService;
import com.aipl.platform.service.RunService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

@RestController
@RequestMapping("/api")
public class PlanController {
    private final PlanService planService;
    private final AssistantService assistantService;
    private final RunService runService;
    private final EnginePaths enginePaths;
    private final String dbPath;
    private final ObjectMapper mapper = new ObjectMapper();

    public PlanController(
            PlanService planService,
            AssistantService assistantService,
            RunService runService,
            EnginePaths enginePaths,
            @Value("${app.dbPath}") String dbPath
    ) {
        this.planService = planService;
        this.assistantService = assistantService;
        this.runService = runService;
        this.enginePaths = enginePaths;
        this.dbPath = dbPath;
    }

    @PostMapping("/plans")
    public ApiResponse<JsonNode> plan(@RequestBody PlanRequest req) throws Exception {
        JsonNode res = planService.plan(req.task, req.planId, req.workspace);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/assistant/chat")
    public ApiResponse<JsonNode> assistantChat(@RequestBody AssistantChatRequest req) throws Exception {
        JsonNode res = assistantService.chat(req.messages, req.message, req.workspace);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/assistant/chat/stream")
    public SseEmitter assistantChatStream(@RequestBody AssistantChatRequest req) throws Exception {
        SseEmitter emitter = new SseEmitter(600000L);
        ObjectNode payload = assistantService.buildPayload(req.messages, req.message);
        Path workspaceDir = enginePaths.getEngineRoot().resolve("artifacts").resolve("assistant");
        Files.createDirectories(workspaceDir);
        Path payloadPath = workspaceDir.resolve("assistant-chat-" + System.currentTimeMillis() + ".json");
        mapper.writeValue(payloadPath.toFile(), payload);

        List<String> cmd = new EngineCommandBuilder("assistant-chat-stream", enginePaths.getEngineRoot().toString())
                .globalArg("--db-path", dbPath)
                .arg("--messages-file", payloadPath.toString())
                .arg("--workspace", req.workspace)
                .build();

        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(enginePaths.getEngineRoot().toFile());
        pb.environment().put("PYTHONUTF8", "1");
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        pb.environment().put("CONDA_AUTO_ACTIVATE_BASE", "false");
        pb.environment().remove("CONDA_SHLVL");
        pb.environment().remove("CONDA_PROMPT_MODIFIER");

        AtomicReference<Process> processRef = new AtomicReference<>();
        emitter.onCompletion(() -> {
            Process proc = processRef.get();
            if (proc != null && proc.isAlive()) {
                proc.destroyForcibly();
            }
        });
        emitter.onTimeout(emitter::complete);

        new Thread(() -> {
            try {
                Process process = pb.start();
                processRef.set(process);
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        if (line.isBlank()) {
                            continue;
                        }
                        String trimmed = line.trim();
                        String eventName = "message";
                        try {
                            JsonNode event = mapper.readTree(trimmed);
                            if (event.has("type")) {
                                eventName = event.get("type").asText("message");
                            }
                        } catch (Exception ignored) {
                        }
                        try {
                            emitter.send(SseEmitter.event().name(eventName).data(trimmed));
                        } catch (Exception sendEx) {
                            emitter.completeWithError(sendEx);
                            return;
                        }
                    }
                }
                process.waitFor();
                emitter.complete();
            } catch (Exception ex) {
                emitter.completeWithError(ex);
            }
        }).start();

        return emitter;
    }

    @PostMapping("/assistant/plan")
    public ApiResponse<JsonNode> assistantPlan(@RequestBody AssistantPlanRequest req) throws Exception {
        String task = assistantService.buildTaskFromMessages(req.messages);
        JsonNode res = planService.plan(task, req.planId, req.workspace);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @GetMapping("/plans")
    public ApiResponse<List<JsonNode>> listPlans(@RequestParam(required = false) String workspace) throws Exception {
        return ApiResponse.ok(planService.listPlans(workspace));
    }

    @GetMapping("/plans/{planId}")
    public ApiResponse<JsonNode> planDetail(@PathVariable String planId) throws Exception {
        return ApiResponse.ok(planService.planDetail(planId));
    }

    /**
     * Starts a run for an existing plan.
     */
    @PostMapping("/plans/{planId}/run")
    public ApiResponse<JsonNode> runPlan(
            @PathVariable String planId,
            @RequestBody(required = false) Map<String, String> body
    ) throws Exception {
        String workspace = body != null ? body.get("workspace") : null;
        String mode = body != null ? body.get("mode") : null;
        if (mode == null || mode.isBlank()) {
            mode = "autopilot";
        }

        JsonNode res = runService.runPlan(planId, workspace, mode);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/plans/{planId}/rework")
    public ApiResponse<JsonNode> reworkPlan(@PathVariable String planId) throws Exception {
        JsonNode res = runService.reworkPlan(planId);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @DeleteMapping("/plans/{planId}")
    public ApiResponse<JsonNode> deletePlan(@PathVariable String planId) throws Exception {
        return ApiResponse.ok(planService.deletePlan(planId));
    }
}
