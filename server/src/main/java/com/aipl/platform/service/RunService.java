package com.aipl.platform.service;

import com.aipl.platform.engine.EngineClient;
import com.aipl.platform.repository.RunRepository;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class RunService {
    private final EngineClient engine;
    private final RunRepository runRepository;

    public RunService(EngineClient engine, RunRepository runRepository) {
        this.engine = engine;
        this.runRepository = runRepository;
    }

    public JsonNode run(String task, String planId, String workspace) throws Exception {
        JsonNode res = engine.run(task, planId, workspace);
        runRepository.upsertRun(res);
        return res;
    }

    public List<JsonNode> listRuns() throws Exception {
        return runRepository.listRunsFromDb();
    }

    public JsonNode status(String planId, String runId) throws Exception {
        JsonNode res = engine.status(planId, runId);
        runRepository.upsertRun(res);
        return res;
    }

    public JsonNode events(String planId, String runId, int cursor, int limit) throws Exception {
        return engine.events(planId, runId, cursor, limit);
    }

    public JsonNode artifacts(String planId, String runId) throws Exception {
        return engine.artifacts(planId, runId);
    }

    public JsonNode cancel(String planId, String runId) throws Exception {
        JsonNode res = engine.cancel(planId, runId);
        runRepository.upsertRun(res);
        return res;
    }

    public JsonNode retry(String planId, String runId, boolean force, boolean retryDeps, String retryIdSuffix, boolean reuseTaskId) throws Exception {
        return engine.retry(planId, runId, force, retryDeps, retryIdSuffix, reuseTaskId);
    }
}
