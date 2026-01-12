package com.aipl.platform.service;

import com.aipl.platform.engine.EngineClient;
import com.aipl.platform.engine.EnginePaths;
import com.aipl.platform.repository.RunRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

@Service
public class RunService {
    private final EngineClient engine;
    private final RunRepository runRepository;
    private final EnginePaths paths;
    private final ObjectMapper mapper = new ObjectMapper();

    public RunService(EngineClient engine, RunRepository runRepository, EnginePaths paths) {
        this.engine = engine;
        this.runRepository = runRepository;
        this.paths = paths;
    }

    private String resolvePlanId(String planId, String runId) {
        if (planId != null && !planId.isBlank()) return planId;
        return paths.resolvePlanIdForRun(runId);
    }

    public JsonNode run(String task, String planId, String workspace, String mode) throws Exception {
        return engine.run(task, planId, workspace, mode);
    }

    public List<JsonNode> listRuns(String workspace) throws Exception {
        return runRepository.listRuns(workspace);
    }

    public JsonNode runPlan(String planId, String workspace, String mode) throws Exception {
        return engine.runPlan(planId, workspace, mode);
    }

    public JsonNode status(String planId, String runId) throws Exception {
        return engine.status(resolvePlanId(planId, runId), runId);
    }

    public JsonNode events(String planId, String runId, int cursor, int limit) throws Exception {
        return engine.events(resolvePlanId(planId, runId), runId, cursor, limit);
    }

    public JsonNode artifacts(String planId, String runId) throws Exception {
        return engine.artifacts(resolvePlanId(planId, runId), runId);
    }

    public JsonNode cancel(String planId, String runId) throws Exception {
        return engine.cancel(resolvePlanId(planId, runId), runId);
    }

    public JsonNode pause(String planId, String runId) throws Exception {
        return engine.pause(resolvePlanId(planId, runId), runId);
    }

    public JsonNode resume(String planId, String runId) throws Exception {
        return engine.resume(resolvePlanId(planId, runId), runId);
    }

    public JsonNode cancelPlanRuns(String planId) throws Exception {
        return engine.cancelPlanRuns(planId);
    }

    public JsonNode apply(String planId, String runId) throws Exception {
        return engine.apply(resolvePlanId(planId, runId), runId);
    }

    public JsonNode discard(String planId, String runId) throws Exception {
        return engine.discard(resolvePlanId(planId, runId), runId);
    }

    public JsonNode rework(String planId, String runId, String stepId, String feedback, String scope) throws Exception {
        return engine.rework(resolvePlanId(planId, runId), runId, stepId, feedback, scope);
    }

    public JsonNode retry(String planId, String runId, boolean force, boolean retryDeps, String retryIdSuffix, boolean reuseTaskId) throws Exception {
        return engine.retry(resolvePlanId(planId, runId), runId, force, retryDeps, retryIdSuffix, reuseTaskId);
    }

    public JsonNode deleteRun(String planId, String runId) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        ObjectNode payload = mapper.createObjectNode();
        payload.put("run_id", runId);
        payload.put("plan_id", resolvedPlanId);
        
        if (runId == null || runId.isBlank()) {
            payload.put("deleted", false);
            return payload;
        }
        
        Path runDir = paths.resolveRunDir(resolvedPlanId, runId);
        if (runDir != null && Files.exists(runDir)) {
            deleteTree(runDir);
        }
        
        runRepository.deleteRun(runId);
        
        payload.put("deleted", true);
        return payload;
    }

    private void deleteTree(Path root) throws Exception {
        if (!Files.exists(root)) return;
        Files.walk(root)
            .sorted((a, b) -> b.getNameCount() - a.getNameCount())
            .forEach(path -> {
                try { Files.deleteIfExists(path); } catch (Exception ignored) {}
            });
    }
}
