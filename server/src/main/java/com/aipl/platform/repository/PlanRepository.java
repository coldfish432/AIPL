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

@Component
public class PlanRepository {
    private final Path dbPath;
    private final EnginePaths paths;
    private final ObjectMapper mapper = new ObjectMapper();

    public PlanRepository(@Value("${app.dbPath}") String dbPath, EnginePaths paths) {
        this.dbPath = Path.of(dbPath).toAbsolutePath();
        this.paths = paths;
    }

    private void ensureSchema(Connection conn) throws SQLException {
        try (Statement stmt = conn.createStatement()) {
            stmt.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    workspace_path TEXT,
                    tasks_count INTEGER DEFAULT 0,
                    input_task TEXT,
                    updated_at INTEGER
                )
            """);
            stmt.execute("CREATE INDEX IF NOT EXISTS idx_plans_ws ON plans(workspace_id)");
        }
    }

    /**
     * List plans filtered by workspace.
     */
    public List<JsonNode> listPlans(String workspace) throws Exception {
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
                sql = "SELECT plan_id, workspace_id, workspace_path, tasks_count, input_task, updated_at FROM plans ORDER BY updated_at DESC";
                stmt = conn.prepareStatement(sql);
            } else {
                sql = "SELECT plan_id, workspace_id, workspace_path, tasks_count, input_task, updated_at FROM plans WHERE workspace_id = ? ORDER BY updated_at DESC";
                stmt = conn.prepareStatement(sql);
                stmt.setString(1, workspaceId);
            }
            
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    ObjectNode node = mapper.createObjectNode();
                    node.put("plan_id", rs.getString("plan_id"));
                    node.put("workspace_id", rs.getString("workspace_id"));
                    node.put("workspace_path", rs.getString("workspace_path"));
                    node.put("tasks_count", rs.getInt("tasks_count"));
                    node.put("input_task", rs.getString("input_task"));
                    node.put("updated_at", rs.getLong("updated_at"));
                    items.add(node);
                }
            }
            stmt.close();
        }
        return items;
    }

    public void deletePlan(String planId) throws Exception {
        if (planId == null || planId.isBlank() || dbPath == null) return;
        
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            ensureSchema(conn);
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM runs WHERE plan_id=?")) {
                stmt.setString(1, planId);
                stmt.executeUpdate();
            }
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM plans WHERE plan_id=?")) {
                stmt.setString(1, planId);
                stmt.executeUpdate();
            }
        }
    }
}
