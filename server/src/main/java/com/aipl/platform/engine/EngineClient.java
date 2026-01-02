package com.aipl.platform.engine;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

@Component
public class EngineClient {
    private final ObjectMapper mapper = new ObjectMapper();
    private final Path engineRoot;

    public EngineClient(@Value("${app.engineRoot}") String engineRoot) {
        this.engineRoot = Path.of(engineRoot).toAbsolutePath().normalize();
    }

    public JsonNode run(String task, String planId, String workspace, String mode, String policy) throws Exception {
        List<String> cmd = new EngineCommandBuilder("run", engineRoot.toString())
                .arg("--task", task)
                .arg("--plan-id", planId)
                .arg("--workspace", workspace)
                .arg("--mode", mode)
                .arg("--policy", policy)
                .build();
        return exec(cmd);
    }

    public JsonNode plan(String task, String planId, String workspace) throws Exception {
        List<String> cmd = new EngineCommandBuilder("plan", engineRoot.toString())
                .arg("--task", task)
                .arg("--plan-id", planId)
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }


    public JsonNode runPlan(String planId, String workspace, String mode, String policy) throws Exception {
        List<String> cmd = new EngineCommandBuilder("run-plan", engineRoot.toString())
                .arg("--plan-id", planId)
                .arg("--workspace", workspace)
                .arg("--mode", mode)
                .arg("--policy", policy)
                .build();
        return exec(cmd);
    }

    public JsonNode status(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("status", engineRoot.toString())
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode events(String planId, String runId, int cursor, int limit) throws Exception {
        List<String> cmd = new EngineCommandBuilder("events", engineRoot.toString())
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .arg("--cursor", String.valueOf(cursor))
                .arg("--limit", String.valueOf(limit))
                .build();
        return exec(cmd);
    }

    public JsonNode artifacts(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("artifacts", engineRoot.toString())
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode cancel(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("cancel", engineRoot.toString())
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode apply(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("apply", engineRoot.toString())
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode discard(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("discard", engineRoot.toString())
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }


    public JsonNode rework(String planId, String runId, String stepId, String feedback, String scope) throws Exception {
        List<String> cmd = new EngineCommandBuilder("rework", engineRoot.toString())
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .arg("--step-id", stepId)
                .arg("--feedback", feedback)
                .arg("--scope", scope)
                .build();
        return exec(cmd);
    }

    public JsonNode retry(String planId, String runId, boolean force, boolean retryDeps, String retryIdSuffix, boolean reuseTaskId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("retry", engineRoot.toString())
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
        List<String> cmd = new EngineCommandBuilder("profile", engineRoot.toString())
                .arg("--action", action)
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }

    public JsonNode assistantChat(JsonNode payload) throws Exception {
        Path dir = engineRoot.resolve("artifacts").resolve("assistant");
        Files.createDirectories(dir);
        Path payloadPath = dir.resolve("assistant-chat-" + System.currentTimeMillis() + ".json");
        mapper.writeValue(payloadPath.toFile(), payload);
        List<String> cmd = new EngineCommandBuilder("assistant-chat", engineRoot.toString())
                .arg("--messages-file", payloadPath.toString())
                .build();
        return exec(cmd);
    }

    private JsonNode exec(List<String> cmd) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(engineRoot.toFile());
        pb.environment().put("PYTHONUTF8", "1");
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        pb.redirectErrorStream(true);
        Process p = pb.start();
        StringBuilder sb = new StringBuilder();
        String lastJsonLine = null;
        try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = r.readLine()) != null) {
                if (!sb.isEmpty()) {
                    sb.append("\n");
                }
                sb.append(line);
                String trimmed = line.trim();
                if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
                    lastJsonLine = trimmed;
                }
            }
        }
        int code = p.waitFor();
        String output = sb.toString().trim();
        if (code != 0) {
            String suffix = output.isEmpty() ? "" : " output: " + output;
            throw new RuntimeException("engine_cli failed: " + code + suffix);
        }
        if (lastJsonLine != null && !lastJsonLine.isBlank()) {
            return mapper.readTree(lastJsonLine);
        }
        if (output.isEmpty()) {
            throw new RuntimeException("engine_cli produced no output");
        }
        return mapper.readTree(output);
    }
}
