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
        JsonNode res = engine.plan(task, planId, workspace);
        runRepository.upsertPlan(res);
        return res;
    }

    public List<JsonNode> listPlans() throws Exception {
        return planRepository.listPlansFromDb();
    }

    public JsonNode planDetail(String planId) throws Exception {
        Path execDir = paths.getEngineRoot().resolve("artifacts").resolve("executions").resolve(planId);
        Path planPath = execDir.resolve("plan.json");
        Path snapshotPath = execDir.resolve("snapshot.json");
        ObjectNode payload = mapper.createObjectNode();
        payload.put("plan_id", planId);
        if (Files.exists(planPath)) {
            payload.set("plan", mapper.readTree(planPath.toFile()));
        }
        if (Files.exists(snapshotPath)) {
            payload.set("snapshot", mapper.readTree(snapshotPath.toFile()));
        }
        return payload;
    }
}
