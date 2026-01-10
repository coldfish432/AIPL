package com.aipl.platform.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Service
public class WorkspaceService {
    private final ObjectMapper mapper = new ObjectMapper();
    private final Path workspaceScript;

    public WorkspaceService(@Value("${app.engineRoot}") String engineRoot) {
        Path root = Path.of(engineRoot).toAbsolutePath().normalize();
        Path candidate = root.resolve("detect_workspace.py");
        if (Files.exists(candidate)) {
            this.workspaceScript = candidate;
        } else {
            Path alt = root.getParent() != null ? root.getParent().resolve("detect_workspace.py") : null;
            if (alt != null && Files.exists(alt)) {
                this.workspaceScript = alt;
            } else {
                throw new IllegalStateException("detect_workspace.py not found near engine root: " + root);
            }
        }
    }

    public JsonNode describeWorkspace(String workspacePath) throws Exception {
        List<String> cmd = new ArrayList<>();
        cmd.add("python");
        cmd.add(workspaceScript.toString());
        cmd.add(workspacePath);
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(workspaceScript.getParent().toFile());
        pb.environment().put("PYTHONUTF8", "1");
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        pb.redirectErrorStream(true);
        Process process = pb.start();
        StringBuilder output = new StringBuilder();
        String line;
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            while ((line = reader.readLine()) != null) {
                output.append(line).append("\n");
            }
        }
        int code = process.waitFor();
        if (code != 0) {
            throw new RuntimeException("detect_workspace failed: " + code + " output: " + output);
        }
        String trimmed = output.toString().trim();
        if (trimmed.isEmpty()) {
            throw new RuntimeException("detect_workspace produced no output");
        }
        return mapper.readTree(trimmed);
    }
}
