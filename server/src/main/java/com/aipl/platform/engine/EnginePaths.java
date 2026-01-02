package com.aipl.platform.engine;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Component
public class EnginePaths {
    private final Path engineRoot;

    public EnginePaths(@Value("${app.engineRoot}") String engineRoot) {
        this.engineRoot = Path.of(engineRoot).toAbsolutePath().normalize();
    }

    public Path getEngineRoot() {
        return engineRoot;
    }

    public Path resolveRunDir(String planId, String runId) {
        if (planId != null && !planId.isBlank()) {
            Path execDir = engineRoot.resolve("artifacts").resolve("executions").resolve(planId);
            if (runId != null && !runId.isBlank()) {
                return execDir.resolve("runs").resolve(runId);
            }
            return execDir.resolve("runs");
        }
        if (runId != null && !runId.isBlank()) {
            String resolvedPlan = resolvePlanIdForRun(runId);
            if (resolvedPlan != null) {
                return engineRoot.resolve("artifacts").resolve("executions").resolve(resolvedPlan).resolve("runs").resolve(runId);
            }
            return engineRoot.resolve("artifacts").resolve("runs").resolve(runId);
        }
        return null;
    }

    public String resolvePlanIdForRun(String runId) {
        if (runId == null || runId.isBlank()) {
            return null;
        }
        Path execRoot = engineRoot.resolve("artifacts").resolve("executions");
        if (!execRoot.toFile().exists()) {
            return null;
        }
        java.io.File[] plans = execRoot.toFile().listFiles();
        if (plans == null) {
            return null;
        }
        for (java.io.File planDir : plans) {
            if (!planDir.isDirectory()) {
                continue;
            }
            Path candidate = planDir.toPath().resolve("runs").resolve(runId);
            if (candidate.toFile().exists()) {
                return planDir.getName();
            }
        }
        return null;
    }

    public List<Path> listRuns(String planId) {
        List<Path> runs = new ArrayList<>();
        Path execDir = engineRoot.resolve("artifacts").resolve("executions").resolve(planId).resolve("runs");
        if (execDir.toFile().exists()) {
            java.io.File[] files = execDir.toFile().listFiles();
            if (files != null) {
                for (java.io.File f : files) {
                    if (f.isDirectory()) {
                        runs.add(f.toPath());
                    }
                }
            }
        }
        return runs;
    }
}
