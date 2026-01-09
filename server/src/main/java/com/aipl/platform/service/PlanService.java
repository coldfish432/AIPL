package com.aipl.platform.service;

import com.aipl.platform.engine.EngineClient;
import com.aipl.platform.engine.EnginePaths;
import com.aipl.platform.repository.PlanRepository;
import com.aipl.platform.repository.RunRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Service
public class PlanService {
    private final EngineClient engine;
    private final RunRepository runRepository;
    private final PlanRepository planRepository;
    private final EnginePaths paths;
    private final ObjectMapper mapper = new ObjectMapper();

    public PlanService(EngineClient engine, RunRepository runRepository, PlanRepository planRepository, EnginePaths paths) {
        this.engine = engine;
        this.runRepository = runRepository;
        this.planRepository = planRepository;
        this.paths = paths;
    }

    public JsonNode plan(String task, String planId, String workspace) throws Exception {
        JsonNode res = engine.plan(task, planId, workspace);
        runRepository.upsertPlan(res);
        return res;
    }

    public List<JsonNode> listPlans(String workspace) throws Exception {
        List<JsonNode> items = planRepository.listPlansFromDb();
        List<JsonNode> filtered = new ArrayList<>();
        String normalizedWorkspace = normalizeWorkspace(workspace);
        for (JsonNode item : items) {
            String planId = item.path("plan_id").asText(null);
            if (planId == null || planId.isBlank()) {
                continue;
            }
            Path execDir = paths.getEngineRoot().resolve("artifacts").resolve("executions").resolve(planId);
            Path planPath = execDir.resolve("plan.json");
            if (!Files.exists(planPath)) {
                continue;
            }
            if (normalizedWorkspace != null && !matchesWorkspace(planPath, execDir, normalizedWorkspace)) {
                continue;
            }
            filtered.add(item);
        }
        return filtered;
    }

    private String normalizeWorkspace(String workspace) {
        if (workspace == null || workspace.isBlank()) {
            return null;
        }
        return workspace.replace("\\", "/").trim().toLowerCase();
    }

    private boolean matchesWorkspace(Path planPath, Path execDir, String normalizedWorkspace) {
        String planWorkspace = readWorkspaceFromPlan(planPath);
        if (planWorkspace != null && planWorkspace.startsWith(normalizedWorkspace)) {
            return true;
        }
        Path runsDir = execDir.resolve("runs");
        if (!Files.exists(runsDir)) {
            return false;
        }
        try {
            return Files.list(runsDir).anyMatch((runDir) -> matchesRunMeta(runDir, normalizedWorkspace));
        } catch (Exception ignored) {
            return false;
        }
    }

    private String readWorkspaceFromPlan(Path planPath) {
        try {
            JsonNode plan = mapper.readTree(planPath.toFile());
            String workspace = extractWorkspace(plan);
            if (workspace != null) {
                return workspace;
            }
            JsonNode planData = plan.get("plan");
            if (planData != null) {
                return extractWorkspace(planData);
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private String extractWorkspace(JsonNode node) {
        if (node == null) {
            return null;
        }
        JsonNode ws = node.get("workspace_path");
        if (ws == null) {
            ws = node.get("workspace");
        }
        if (ws != null && ws.isTextual()) {
            return ws.asText().replace("\\", "/").trim().toLowerCase();
        }
        return null;
    }

    private boolean matchesRunMeta(Path runDir, String normalizedWorkspace) {
        Path metaPath = runDir.resolve("meta.json");
        if (!Files.exists(metaPath)) {
            return false;
        }
        try {
            JsonNode meta = mapper.readTree(metaPath.toFile());
            String mainRoot = meta.path("workspace_main_root").asText(null);
            String stageRoot = meta.path("workspace_stage_root").asText(null);
            if (mainRoot != null && normalizeWorkspace(mainRoot).startsWith(normalizedWorkspace)) {
                return true;
            }
            return stageRoot != null && normalizeWorkspace(stageRoot).startsWith(normalizedWorkspace);
        } catch (Exception ignored) {
            return false;
        }
    }

    public JsonNode planDetail(String planId) throws Exception {
        Path execDir = paths.getEngineRoot().resolve("artifacts").resolve("executions").resolve(planId);
        Path planPath = execDir.resolve("plan.json");
        Path planTextPath = execDir.resolve("plan.txt");
        Path snapshotPath = execDir.resolve("snapshot.json");
        Path backlogPath = paths.getEngineRoot().resolve("backlog").resolve(planId + ".json");
        ObjectNode payload = mapper.createObjectNode();
        payload.put("plan_id", planId);
        if (Files.exists(planPath)) {
            payload.set("plan", mapper.readTree(planPath.toFile()));
        }
        if (Files.exists(planTextPath)) {
            String planText = Files.readString(planTextPath);
            payload.put("task_chain_text", planText);
        }
        if (Files.exists(snapshotPath)) {
            payload.set("snapshot", mapper.readTree(snapshotPath.toFile()));
        } else if (Files.exists(backlogPath)) {
            ObjectNode snapshot = mapper.createObjectNode();
            snapshot.put("plan_id", planId);
            snapshot.put("snapshot_ts", System.currentTimeMillis() / 1000.0);
            snapshot.put("stop_reason", "backlog_fallback");
            JsonNode backlog = mapper.readTree(backlogPath.toFile());
            if (backlog != null && backlog.has("tasks")) {
                snapshot.set("tasks", backlog.get("tasks"));
            }
            payload.set("snapshot", snapshot);
        }
        return payload;
    }

    public JsonNode deletePlan(String planId) throws Exception {
        ObjectNode payload = mapper.createObjectNode();
        payload.put("plan_id", planId);
        if (planId == null || planId.isBlank()) {
            payload.put("deleted", false);
            return payload;
        }
        Path execDir = paths.getEngineRoot().resolve("artifacts").resolve("executions").resolve(planId);
        if (Files.exists(execDir)) {
            deleteTree(execDir);
        }
        runRepository.deleteRunsByPlan(planId);
        planRepository.deletePlan(planId);
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
