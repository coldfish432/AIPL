package com.aipl.platform.engine;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

/**
 * engine paths helper
 * artifacts/workspaces/{workspace_id}/executions/{plan_id}/runs/{run_id}/
 * artifacts/workspaces/{workspace_id}/backlog/{plan_id}.json
 */
@Component
public class EnginePaths {
    private final Path engineRoot;

    public EnginePaths(@Value("${app.engineRoot}") String engineRoot) {
        this.engineRoot = Path.of(engineRoot).toAbsolutePath().normalize();
    }

    public Path getEngineRoot() {
        return engineRoot;
    }

    public String normalizeWorkspace(String workspace) {
        if (workspace == null || workspace.isBlank()) return "";
        String s = workspace.replace("\\", "/").trim();
        if (System.getProperty("os.name").toLowerCase().contains("win")) {
            s = s.toLowerCase();
        }
        return s;
    }

    public String computeWorkspaceId(String workspace) {
        if (workspace == null || workspace.isBlank()) return "_default";
        try {
            String normalized = normalizeWorkspace(workspace);
            if (normalized.isEmpty()) return "_default";
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(normalized.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 8; i++) {
                String hex = Integer.toHexString(0xff & hash[i]);
                if (hex.length() == 1) sb.append('0');
                sb.append(hex);
            }
            return sb.toString();
        } catch (Exception e) {
            return "_default";
        }
    }

    public Path getWorkspaceDir(String workspace) {
        return engineRoot.resolve("artifacts").resolve("workspaces").resolve(computeWorkspaceId(workspace));
    }

    public Path getPlanDir(String workspace, String planId) {
        return getWorkspaceDir(workspace).resolve("executions").resolve(planId);
    }

    public Path getRunDir(String workspace, String planId, String runId) {
        return getPlanDir(workspace, planId).resolve("runs").resolve(runId);
    }

    public Path resolveRunDir(String planId, String runId) {
        if (runId == null || runId.isBlank()) return null;
        
        Path wsRoot = engineRoot.resolve("artifacts").resolve("workspaces");
        if (!Files.exists(wsRoot)) return null;
        
        try {
            for (Path wsDir : Files.newDirectoryStream(wsRoot)) {
                if (!Files.isDirectory(wsDir)) continue;
                Path execsDir = wsDir.resolve("executions");
                if (!Files.exists(execsDir)) continue;
                
                if (planId != null && !planId.isBlank()) {
                    Path runDir = execsDir.resolve(planId).resolve("runs").resolve(runId);
                    if (Files.exists(runDir)) return runDir;
                } else {
                    for (Path pDir : Files.newDirectoryStream(execsDir)) {
                        if (!Files.isDirectory(pDir)) continue;
                        Path runDir = pDir.resolve("runs").resolve(runId);
                        if (Files.exists(runDir)) return runDir;
                    }
                }
            }
        } catch (Exception ignored) {}
        return null;
    }

    public String resolvePlanIdForRun(String runId) {
        if (runId == null || runId.isBlank()) return null;
        
        Path wsRoot = engineRoot.resolve("artifacts").resolve("workspaces");
        if (!Files.exists(wsRoot)) return null;
        
        try {
            for (Path wsDir : Files.newDirectoryStream(wsRoot)) {
                if (!Files.isDirectory(wsDir)) continue;
                Path execsDir = wsDir.resolve("executions");
                if (!Files.exists(execsDir)) continue;
                
                for (Path pDir : Files.newDirectoryStream(execsDir)) {
                    if (!Files.isDirectory(pDir)) continue;
                    if (Files.exists(pDir.resolve("runs").resolve(runId))) {
                        return pDir.getFileName().toString();
                    }
                }
            }
        } catch (Exception ignored) {}
        return null;
    }

    public List<Path> listRuns(String planId) {
        List<Path> runs = new ArrayList<>();
        if (planId == null || planId.isBlank()) return runs;
        
        Path wsRoot = engineRoot.resolve("artifacts").resolve("workspaces");
        if (!Files.exists(wsRoot)) return runs;
        
        try {
            for (Path wsDir : Files.newDirectoryStream(wsRoot)) {
                if (!Files.isDirectory(wsDir)) continue;
                Path runsDir = wsDir.resolve("executions").resolve(planId).resolve("runs");
                if (!Files.exists(runsDir)) continue;
                
                for (Path r : Files.newDirectoryStream(runsDir)) {
                    if (Files.isDirectory(r)) runs.add(r);
                }
            }
        } catch (Exception ignored) {}
        return runs;
    }
}
