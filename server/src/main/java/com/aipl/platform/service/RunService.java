package com.aipl.platform.service;

import com.aipl.platform.engine.EngineClient;
import com.aipl.platform.engine.EnginePaths;
import com.aipl.platform.repository.RunRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Service
public class RunService {
    private final EngineClient engine;
    private final RunRepository runRepository;
    private final EnginePaths paths;

    public RunService(EngineClient engine, RunRepository runRepository, EnginePaths paths) {
        this.engine = engine;
        this.runRepository = runRepository;
        this.paths = paths;
    }

    private String resolvePlanId(String planId, String runId) {
        if (planId != null && !planId.isBlank()) {
            return planId;
        }
        return paths.resolvePlanIdForRun(runId);
    }

    public JsonNode run(String task, String planId, String workspace, String mode, String policy) throws Exception {
        JsonNode res = engine.run(task, planId, workspace, mode, policy);
        runRepository.upsertRun(res);
        return res;
    }

    public List<JsonNode> listRuns() throws Exception {
        List<JsonNode> items = runRepository.listRunsFromDb();
        List<JsonNode> filtered = new ArrayList<>();
        for (JsonNode item : items) {
            String runId = item.path("run_id").asText(null);
            String planId = item.path("plan_id").asText(null);
            if (planId == null || planId.isBlank()) {
                planId = resolvePlanId(planId, runId);
                if (planId != null && item.isObject()) {
                    ((ObjectNode) item).put("plan_id", planId);
                }
            }
            if (runId == null || runId.isBlank() || planId == null || planId.isBlank()) {
                continue;
            }
            Path runDir = paths.resolveRunDir(planId, runId);
            if (runDir != null && Files.exists(runDir)) {
                filtered.add(item);
            }
        }
        return filtered;
    }


    public JsonNode runPlan(String planId, String workspace, String mode, String policy) throws Exception {
        JsonNode res = engine.runPlan(planId, workspace, mode, policy);
        runRepository.upsertRun(res);
        return res;
    }

    public JsonNode status(String planId, String runId) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        JsonNode res = engine.status(resolvedPlanId, runId);
        runRepository.upsertRun(res);
        return res;
    }

    public JsonNode events(String planId, String runId, int cursor, int limit) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        return engine.events(resolvedPlanId, runId, cursor, limit);
    }

    public JsonNode artifacts(String planId, String runId) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        return engine.artifacts(resolvedPlanId, runId);
    }

    public JsonNode cancel(String planId, String runId) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        JsonNode res = engine.cancel(resolvedPlanId, runId);
        runRepository.upsertRun(res);
        return res;
    }

    public JsonNode apply(String planId, String runId) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        JsonNode res = engine.apply(resolvedPlanId, runId);
        runRepository.upsertRun(res);
        return res;
    }

    public JsonNode discard(String planId, String runId) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        JsonNode res = engine.discard(resolvedPlanId, runId);
        runRepository.upsertRun(res);
        return res;
    }


    public JsonNode rework(String planId, String runId, String stepId, String feedback, String scope) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        JsonNode res = engine.rework(resolvedPlanId, runId, stepId, feedback, scope);
        runRepository.upsertRun(res);
        return res;
    }

    public JsonNode retry(String planId, String runId, boolean force, boolean retryDeps, String retryIdSuffix, boolean reuseTaskId) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        return engine.retry(resolvedPlanId, runId, force, retryDeps, retryIdSuffix, reuseTaskId);
    }

    public JsonNode deleteRun(String planId, String runId) throws Exception {
        String resolvedPlanId = resolvePlanId(planId, runId);
        ObjectNode payload = new com.fasterxml.jackson.databind.ObjectMapper().createObjectNode();
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
        if (!Files.exists(root)) {
            return;
        }
        Files.walk(root)
                .sorted((a, b) -> b.getNameCount() - a.getNameCount())
                .forEach(path -> {
                    try {
                        Files.deleteIfExists(path);
                    } catch (Exception ignored) {
                    }
                });
    }
}
