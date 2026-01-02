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

    public List<JsonNode> listPlans() throws Exception {
        List<JsonNode> items = planRepository.listPlansFromDb();
        List<JsonNode> filtered = new ArrayList<>();
        for (JsonNode item : items) {
            String planId = item.path("plan_id").asText(null);
            if (planId == null || planId.isBlank()) {
                continue;
            }
            Path planPath = paths.getEngineRoot().resolve("artifacts").resolve("executions").resolve(planId).resolve("plan.json");
            if (Files.exists(planPath)) {
                filtered.add(item);
            }
        }
        return filtered;
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
