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
    private final String dbPath;

    public EngineClient(
            @Value("${app.engineRoot}") String engineRoot,
            @Value("${app.dbPath}") String dbPath
    ) {
        this.engineRoot = Path.of(engineRoot).toAbsolutePath().normalize();
        this.dbPath = Path.of(dbPath).toAbsolutePath().toString();
    }

    public JsonNode run(String task, String planId, String workspace, String mode) throws Exception {
        List<String> cmd = new EngineCommandBuilder("run", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--task", task)
                .arg("--plan-id", planId)
                .arg("--workspace", workspace)
                .arg("--mode", mode)
                .build();
        return exec(cmd);
    }

    public JsonNode plan(String task, String planId, String workspace) throws Exception {
        List<String> cmd = new EngineCommandBuilder("plan", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--task", task)
                .arg("--plan-id", planId)
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }


    public JsonNode runPlan(String planId, String workspace, String mode) throws Exception {
        List<String> cmd = new EngineCommandBuilder("run-plan", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--workspace", workspace)
                .arg("--mode", mode)
                .build();
        return exec(cmd);
    }

    public JsonNode status(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("status", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode events(String planId, String runId, int cursor, int limit) throws Exception {
        List<String> cmd = new EngineCommandBuilder("events", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .arg("--cursor", String.valueOf(cursor))
                .arg("--limit", String.valueOf(limit))
                .build();
        return exec(cmd);
    }

    public JsonNode artifacts(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("artifacts", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode cancel(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("cancel", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode pause(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("pause", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode resume(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("resume", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode cancelPlanRuns(String planId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("cancel-plan-runs", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .build();
        return exec(cmd);
    }

    public JsonNode apply(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("apply", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }

    public JsonNode discard(String planId, String runId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("discard", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--plan-id", planId)
                .arg("--run-id", runId)
                .build();
        return exec(cmd);
    }


    public JsonNode rework(String planId, String runId, String stepId, String feedback, String scope) throws Exception {
        List<String> cmd = new EngineCommandBuilder("rework", engineRoot.toString())
                .globalArg("--db-path", dbPath)
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
                .globalArg("--db-path", dbPath)
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
                .globalArg("--db-path", dbPath)
                .arg("--action", action)
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }

    public JsonNode profileUpdate(String workspace, JsonNode userHard) throws Exception {
        Path payloadPath = writePayload(
                "profile",
                mapper.createObjectNode().set("user_hard", userHard == null ? mapper.nullNode() : userHard)
        );
        List<String> cmd = new EngineCommandBuilder("profile", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--action", "update")
                .arg("--workspace", workspace)
                .arg("--payload", payloadPath.toString())
                .build();
        return exec(cmd);
    }

    public JsonNode assistantChat(JsonNode payload, String workspace) throws Exception {
        Path dir = engineRoot.resolve("artifacts").resolve("assistant");
        Files.createDirectories(dir);
        Path payloadPath = dir.resolve("assistant-chat-" + System.currentTimeMillis() + ".json");
        mapper.writeValue(payloadPath.toFile(), payload);
        List<String> cmd = new EngineCommandBuilder("assistant-chat", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--messages-file", payloadPath.toString())
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }

    private Path writePayload(String prefix, JsonNode payload) throws Exception {
        Path dir = engineRoot.resolve("artifacts").resolve("assistant");
        Files.createDirectories(dir);
        Path payloadPath = dir.resolve(prefix + "-" + System.currentTimeMillis() + ".json");
        mapper.writeValue(payloadPath.toFile(), payload);
        return payloadPath;
    }

    public JsonNode languagePacks(
            String action,
            String packId,
            JsonNode payload,
            String name,
            String description,
            Boolean enabled,
            String workspace
    ) throws Exception {
        Path payloadPath = payload != null ? writePayload("language-pack", payload) : null;
        String enabledValue = enabled != null ? (enabled ? "1" : "0") : null;
        List<String> cmd = new EngineCommandBuilder("language-packs", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--action", action)
                .arg("--pack-id", packId)
                .arg("--payload", payloadPath != null ? payloadPath.toString() : null)
                .arg("--name", name)
                .arg("--description", description)
                .arg("--enabled", enabledValue)
                .arg("--workspace", workspace)
                .build();
        return exec(cmd);
    }

    public JsonNode memory(String workspaceId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("memory", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--workspace-id", workspaceId)
                .build();
        return exec(cmd);
    }

    public JsonNode experiencePacks(
            String action,
            String workspaceId,
            String packId,
            JsonNode payload,
            String fromWorkspaceId,
            Boolean includeRules,
            Boolean includeChecks,
            Boolean includeLessons,
            Boolean includePatterns,
            String name,
            String description,
            Boolean enabled
    ) throws Exception {
        Path payloadPath = payload != null ? writePayload("experience-pack", payload) : null;
        String enabledValue = enabled != null ? (enabled ? "1" : "0") : null;
        List<String> cmd = new EngineCommandBuilder("experience-packs", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--action", action)
                .arg("--workspace-id", workspaceId)
                .arg("--pack-id", packId)
                .arg("--payload", payloadPath != null ? payloadPath.toString() : null)
                .arg("--from-workspace-id", fromWorkspaceId)
                .flag("--include-rules", includeRules != null && includeRules)
                .flag("--include-checks", includeChecks != null && includeChecks)
                .flag("--include-lessons", includeLessons != null && includeLessons)
                .flag("--include-patterns", includePatterns != null && includePatterns)
                .arg("--name", name)
                .arg("--description", description)
                .arg("--enabled", enabledValue)
                .build();
        return exec(cmd);
    }

    public JsonNode rules(String action, String workspaceId, String ruleId, String content, String scope, String category) throws Exception {
        List<String> cmd = new EngineCommandBuilder("rules", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--action", action)
                .arg("--workspace-id", workspaceId)
                .arg("--rule-id", ruleId)
                .arg("--content", content)
                .arg("--scope", scope)
                .arg("--category", category)
                .build();
        return exec(cmd);
    }

    public JsonNode checks(String action, String workspaceId, String checkId, JsonNode payload, String scope) throws Exception {
        Path payloadPath = payload != null ? writePayload("checks", payload) : null;
        List<String> cmd = new EngineCommandBuilder("checks", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--action", action)
                .arg("--workspace-id", workspaceId)
                .arg("--check-id", checkId)
                .arg("--payload", payloadPath != null ? payloadPath.toString() : null)
                .arg("--scope", scope)
                .build();
        return exec(cmd);
    }

    public JsonNode lessons(String action, String workspaceId, String lessonId) throws Exception {
        List<String> cmd = new EngineCommandBuilder("lessons", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--action", action)
                .arg("--workspace-id", workspaceId)
                .arg("--lesson-id", lessonId)
                .build();
        return exec(cmd);
    }

    public JsonNode workspaceTree(String workspace, int depth) throws Exception {
        List<String> cmd = new EngineCommandBuilder("workspace-tree", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--workspace", workspace)
                .arg("--depth", String.valueOf(depth))
                .build();
        return exec(cmd);
    }

    public JsonNode workspaceRead(String workspace, String path) throws Exception {
        List<String> cmd = new EngineCommandBuilder("workspace-read", engineRoot.toString())
                .globalArg("--db-path", dbPath)
                .arg("--workspace", workspace)
                .arg("--path", path)
                .build();
        return exec(cmd);
    }

    private JsonNode exec(List<String> cmd) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(engineRoot.toFile());
        pb.environment().put("PYTHONUTF8", "1");
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        // 禁用 conda 自动激活并移除可能冲突的环境变量
        pb.environment().put("CONDA_AUTO_ACTIVATE_BASE", "false");
        pb.environment().remove("CONDA_SHLVL");
        pb.environment().remove("CONDA_PROMPT_MODIFIER");
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
