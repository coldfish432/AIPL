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
        return engine.plan(task, planId, workspace);
    }

    /**
     * List plans - read directly from database and filter by workspace.
     */
    public List<JsonNode> listPlans(String workspace) throws Exception {
        return planRepository.listPlans(workspace);
    }

    /**
     * Get plan details.
     */
    public JsonNode planDetail(String planId) throws Exception {
        // Walk workspaces to find plan
        Path wsRoot = paths.getEngineRoot().resolve("artifacts").resolve("workspaces");
        Path execDir = null;
        
        if (Files.exists(wsRoot)) {
            try (var stream = Files.newDirectoryStream(wsRoot)) {
                for (Path wsDir : stream) {
                    if (!Files.isDirectory(wsDir)) continue;
                    Path candidate = wsDir.resolve("executions").resolve(planId);
                    if (Files.exists(candidate)) {
                        execDir = candidate;
                        break;
                    }
                }
            }
        }
        
        ObjectNode payload = mapper.createObjectNode();
        payload.put("plan_id", planId);
        
        if (execDir == null) {
            return payload;
        }
        
        Path planPath = execDir.resolve("plan.json");
        Path planTextPath = execDir.resolve("plan.txt");
        Path snapshotPath = execDir.resolve("snapshot.json");
        
        if (Files.exists(planPath)) {
            payload.set("plan", mapper.readTree(planPath.toFile()));
        }
        if (Files.exists(planTextPath)) {
            payload.put("task_chain_text", Files.readString(planTextPath));
        }
        if (Files.exists(snapshotPath)) {
            payload.set("snapshot", mapper.readTree(snapshotPath.toFile()));
        } else {
            Path backlogDir = execDir.getParent().getParent().resolve("backlog");
            Path backlogPath = backlogDir.resolve(planId + ".json");
            if (Files.exists(backlogPath)) {
                ObjectNode snapshot = mapper.createObjectNode();
                snapshot.put("plan_id", planId);
                snapshot.put("snapshot_ts", System.currentTimeMillis() / 1000.0);
                JsonNode backlog = mapper.readTree(backlogPath.toFile());
                if (backlog.has("tasks")) {
                    snapshot.set("tasks", backlog.get("tasks"));
                }
                payload.set("snapshot", snapshot);
            }
        }
        
        return payload;
    }

    /**
     * Delete plan.
     */
    public JsonNode deletePlan(String planId) throws Exception {
        ObjectNode payload = mapper.createObjectNode();
        payload.put("plan_id", planId);
        
        if (planId == null || planId.isBlank()) {
            payload.put("deleted", false);
            return payload;
        }
        
        Path wsRoot = paths.getEngineRoot().resolve("artifacts").resolve("workspaces");
        if (Files.exists(wsRoot)) {
            try (var stream = Files.newDirectoryStream(wsRoot)) {
                for (Path wsDir : stream) {
                    if (!Files.isDirectory(wsDir)) continue;
                    
                    Path execDir = wsDir.resolve("executions").resolve(planId);
                    if (Files.exists(execDir)) {
                        deleteTree(execDir);
                    }
                    
                    Path backlogPath = wsDir.resolve("backlog").resolve(planId + ".json");
                    Files.deleteIfExists(backlogPath);
                }
            }
        }
        
        runRepository.deleteRunsByPlan(planId);
        planRepository.deletePlan(planId);
        
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
