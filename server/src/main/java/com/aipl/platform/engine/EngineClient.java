package com.aipl.platform.engine;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Component
public class EngineClient {
    private final ObjectMapper mapper = new ObjectMapper();
    private final Path engineRoot;

    public EngineClient(@Value("${app.engineRoot}") String engineRoot) {
        this.engineRoot = Path.of(engineRoot).toAbsolutePath().normalize();
    }

    public JsonNode run(String goal, String planId, String workspace) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add("engine_cli.py");
        cmd.add("run");
        cmd.add("--goal");
        cmd.add(goal);
        if (planId != null && !planId.isBlank()) {
            cmd.add("--plan-id");
            cmd.add(planId);
        }
        if (workspace != null && !workspace.isBlank()) {
            cmd.add("--workspace");
            cmd.add(workspace);
        }
        return exec(cmd);
    }

    public JsonNode plan(String goal, String planId, String workspace) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add("engine_cli.py");
        cmd.add("plan");
        cmd.add("--goal");
        cmd.add(goal);
        if (planId != null && !planId.isBlank()) {
            cmd.add("--plan-id");
            cmd.add(planId);
        }
        if (workspace != null && !workspace.isBlank()) {
            cmd.add("--workspace");
            cmd.add(workspace);
        }
        return exec(cmd);
    }

    public JsonNode status(String planId, String runId) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add("engine_cli.py");
        cmd.add("status");
        if (planId != null && !planId.isBlank()) {
            cmd.add("--plan-id");
            cmd.add(planId);
        }
        if (runId != null && !runId.isBlank()) {
            cmd.add("--run-id");
            cmd.add(runId);
        }
        return exec(cmd);
    }

    public JsonNode events(String planId, String runId, int cursor, int limit) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add("engine_cli.py");
        cmd.add("events");
        if (planId != null && !planId.isBlank()) {
            cmd.add("--plan-id");
            cmd.add(planId);
        }
        if (runId != null && !runId.isBlank()) {
            cmd.add("--run-id");
            cmd.add(runId);
        }
        cmd.add("--cursor");
        cmd.add(String.valueOf(cursor));
        cmd.add("--limit");
        cmd.add(String.valueOf(limit));
        return exec(cmd);
    }

    public JsonNode artifacts(String planId, String runId) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add("engine_cli.py");
        cmd.add("artifacts");
        if (planId != null && !planId.isBlank()) {
            cmd.add("--plan-id");
            cmd.add(planId);
        }
        if (runId != null && !runId.isBlank()) {
            cmd.add("--run-id");
            cmd.add(runId);
        }
        return exec(cmd);
    }

    public JsonNode cancel(String planId, String runId) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add("engine_cli.py");
        cmd.add("cancel");
        if (planId != null && !planId.isBlank()) {
            cmd.add("--plan-id");
            cmd.add(planId);
        }
        if (runId != null && !runId.isBlank()) {
            cmd.add("--run-id");
            cmd.add(runId);
        }
        return exec(cmd);
    }

    public JsonNode retry(String planId, String runId, boolean force, boolean retryDeps, String retryIdSuffix, boolean reuseTaskId) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add("engine_cli.py");
        cmd.add("retry");
        if (planId != null && !planId.isBlank()) {
            cmd.add("--plan-id");
            cmd.add(planId);
        }
        if (runId != null && !runId.isBlank()) {
            cmd.add("--run-id");
            cmd.add(runId);
        }
        if (force) {
            cmd.add("--force");
        }
        if (retryDeps) {
            cmd.add("--retry-deps");
        }
        if (reuseTaskId) {
            cmd.add("--reuse-task-id");
        }
        if (retryIdSuffix != null && !retryIdSuffix.isBlank()) {
            cmd.add("--retry-id-suffix");
            cmd.add(retryIdSuffix);
        }
        return exec(cmd);
    }

    public JsonNode profile(String action, String workspace) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add("engine_cli.py");
        cmd.add("profile");
        cmd.add("--action");
        cmd.add(action);
        cmd.add("--workspace");
        cmd.add(workspace);
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
