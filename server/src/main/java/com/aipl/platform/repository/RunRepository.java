package com.aipl.platform.repository;

import com.aipl.platform.engine.EnginePaths;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Component
public class RunRepository {
    private final ConcurrentMap<String, Integer> cursors = new ConcurrentHashMap<>();
    private final Path dbPath;
    private final EnginePaths paths;
    private final ObjectMapper mapper = new ObjectMapper();

    public RunRepository(@Value("${app.dbPath}") String dbPath, EnginePaths paths) {
        this.dbPath = Path.of(dbPath).toAbsolutePath();
        this.paths = paths;
    }

    private void ensureSchema(Connection conn) throws SQLException {
        try (Statement stmt = conn.createStatement()) {
            stmt.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    workspace_path TEXT,
                    status TEXT DEFAULT 'unknown',
                    task TEXT,
                    updated_at INTEGER
                )
            """);
            stmt.execute("CREATE INDEX IF NOT EXISTS idx_runs_ws ON runs(workspace_id)");
            stmt.execute("CREATE INDEX IF NOT EXISTS idx_runs_plan ON runs(plan_id)");
        }
    }

    public int getCursor(String runId) {
        return runId == null ? 0 : cursors.getOrDefault(runId, 0);
    }

    public void setCursor(String runId, int cursor) {
        if (runId != null) cursors.put(runId, cursor);
    }

    /**
     * List runs filtered by workspace.
     */
    public List<JsonNode> listRuns(String workspace) throws Exception {
        if (dbPath == null || !Files.exists(dbPath)) {
            return List.of();
        }
        
        String workspaceId = paths.computeWorkspaceId(workspace);
        List<JsonNode> items = new ArrayList<>();
        
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            ensureSchema(conn);
            
            String sql;
            PreparedStatement stmt;
            
            if (workspace == null || workspace.isBlank()) {
                sql = "SELECT run_id, plan_id, workspace_id, workspace_path, status, task, updated_at FROM runs ORDER BY updated_at DESC";
                stmt = conn.prepareStatement(sql);
            } else {
                sql = "SELECT run_id, plan_id, workspace_id, workspace_path, status, task, updated_at FROM runs WHERE workspace_id = ? ORDER BY updated_at DESC";
                stmt = conn.prepareStatement(sql);
                stmt.setString(1, workspaceId);
            }
            
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    ObjectNode node = mapper.createObjectNode();
                    node.put("run_id", rs.getString("run_id"));
                    node.put("plan_id", rs.getString("plan_id"));
                    node.put("workspace_id", rs.getString("workspace_id"));
                    node.put("workspace_path", rs.getString("workspace_path"));
                    node.put("status", rs.getString("status"));
                    node.put("task", rs.getString("task"));
                    node.put("updated_at", rs.getLong("updated_at"));
                    items.add(node);
                }
            }
            stmt.close();
        }
        return items;
    }

    public void deleteRun(String runId) throws Exception {
        if (runId == null || runId.isBlank() || dbPath == null) return;
        cursors.remove(runId);
        
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            ensureSchema(conn);
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM runs WHERE run_id=?")) {
                stmt.setString(1, runId);
                stmt.executeUpdate();
            }
        }
    }

    public void deleteRunsByPlan(String planId) throws Exception {
        if (planId == null || planId.isBlank() || dbPath == null) return;
        
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            ensureSchema(conn);
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM runs WHERE plan_id=?")) {
                stmt.setString(1, planId);
                stmt.executeUpdate();
            }
        }
    }

    public String findLatestRunIdByPlan(String planId) throws Exception {
        if (planId == null || planId.isBlank() || dbPath == null) return null;

        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            ensureSchema(conn);
            try (PreparedStatement stmt = conn.prepareStatement(
                "SELECT run_id FROM runs WHERE plan_id=? ORDER BY updated_at DESC LIMIT 1"
            )) {
                stmt.setString(1, planId);
                try (ResultSet rs = stmt.executeQuery()) {
                    if (rs.next()) {
                        return rs.getString("run_id");
                    }
                }
            }
        }

        return null;
    }
}
