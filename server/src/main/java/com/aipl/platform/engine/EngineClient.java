package com.aipl.platform.engine;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.util.List;

@Component
public class EngineClient {
    private final ObjectMapper mapper = new ObjectMapper();
    private final Path engineRoot;

    public EngineClient(@Value("${app.engineRoot}") String engineRoot) {
        this.engineRoot = Path.of(engineRoot).toAbsolutePath().normalize();
    }

    public JsonNode run(String task, String planId, String workspace) throws Exception {
        List<String> cmd = new EngineCommandBuilder("run")
                .arg("--task", task)
                .arg("--plan-id", planId)
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }

    public JsonNode plan(String task, String planId, String workspace) throws Exception {
        List<String> cmd = new EngineCommandBuilder("plan")
                .arg("--task", task)
                .arg("--plan-id", planId)
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }

    public JsonNode status(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("status")
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode events(String planId, String runId, int cursor, int limit) throws Exception {
        List<String> cmd = new EngineCommandBuilder("events")
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .arg("--cursor", String.valueOf(cursor))
                .arg("--limit", String.valueOf(limit))
                .build();
        return exec(cmd);
    }

    public JsonNode artifacts(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("artifacts")
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode cancel(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("cancel")
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode retry(String planId, String runId, boolean force, boolean retryDeps, String retryIdSuffix, boolean reuseTaskId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("retry")
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .flag("--force", force)
                .flag("--retry-deps", retryDeps)
                .flag("--reuse-task-id", reuseTaskId)
                .arg("--retry-id-suffix", retryIdSuffix)
                .build();
        return exec(cmd);
    }

    public JsonNode profile(String action, String workspace) throws Exception {
        List<String> cmd = new EngineCommandBuilder("profile")
                .arg("--action", action)
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }

    private JsonNode exec(List<String> cmd) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(engineRoot.toFile());
        Process p = pb.start();
        StringBuilder sb = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()))) {
            String line;
            while ((line = r.readLine()) != null) {
                sb.append(line);
            }
        }
        int code = p.waitFor();
        if (code != 0) {
            throw new RuntimeException("engine_cli failed: " + code);
        }
        return mapper.readTree(sb.toString());
    }
}
