package com.aipl.platform.repository;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Component
public class RunRepository {
    private final ConcurrentMap<String, Integer> cursors = new ConcurrentHashMap<>();
    private final Path dbPath;
    private final ObjectMapper mapper = new ObjectMapper();

    public RunRepository(@Value("${app.dbPath}") String dbPath) {
        Path configured = Path.of(dbPath).toAbsolutePath();
        this.dbPath = configured;
    }

    public void upsertRun(JsonNode res) throws Exception {
        // no-op: Python is the source of truth and mirrors into SQLite.
    }


    public int getCursor(String runId) throws Exception {
        if (runId == null) {
            return 0;
        }
        return cursors.getOrDefault(runId, 0);
    }

    public void setCursor(String runId, int cursor) throws Exception {
        if (runId == null) {
            return;
        }
        cursors.put(runId, cursor);
    }

    public void upsertPlan(JsonNode res) throws Exception {
        // no-op: Python is the source of truth and mirrors into SQLite.
    }

    public List<JsonNode> listRunsFromDb() throws Exception {
        if (dbPath == null || !Files.exists(dbPath)) {
            return List.of();
        }
        List<JsonNode> items = new ArrayList<>();
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            try (Statement init = conn.createStatement()) {
                init.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_id TEXT, status TEXT, updated_at INTEGER, raw_json TEXT)");
            }
            try (PreparedStatement stmt = conn.prepareStatement("SELECT run_id, plan_id, status, updated_at, raw_json FROM runs ORDER BY updated_at DESC");
                 ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    String runId = rs.getString("run_id");
                    String planId = rs.getString("plan_id");
                    String status = rs.getString("status");
                    long updatedAt = rs.getLong("updated_at");
                    String rawJson = rs.getString("raw_json");
                    ObjectNode node = mapper.createObjectNode();
                    if (rawJson != null && !rawJson.isBlank()) {
                        try {
                            JsonNode raw = mapper.readTree(rawJson);
                            JsonNode data = raw.get("data");
                            if (data != null && data.isObject()) {
                                node.setAll((ObjectNode) data);
                            }
                        } catch (Exception ignored) {
                        }
                    }
                    if (!node.has("run_id") && runId != null) {
                        node.put("run_id", runId);
                    }
                    if (!node.has("plan_id") && planId != null) {
                        node.put("plan_id", planId);
                    }
                    if (!node.has("status") && status != null) {
                        node.put("status", status);
                    }
                    node.put("updated_at", updatedAt);
                    items.add(node);
                }
            }
        }
        return items;
    }

    public void deleteRun(String runId) throws Exception {
        if (runId == null || runId.isBlank() || dbPath == null) {
            return;
        }
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            try (Statement init = conn.createStatement()) {
                init.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_id TEXT, status TEXT, updated_at INTEGER, raw_json TEXT)");
                init.execute("CREATE TABLE IF NOT EXISTS event_cursors (run_id TEXT PRIMARY KEY, cursor INTEGER, updated_at INTEGER)");
            }
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM event_cursors WHERE run_id=?")) {
                stmt.setString(1, runId);
                stmt.executeUpdate();
            }
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM runs WHERE run_id=?")) {
                stmt.setString(1, runId);
                stmt.executeUpdate();
            }
        }
    }

    public void deleteRunsByPlan(String planId) throws Exception {
        if (planId == null || planId.isBlank() || dbPath == null) {
            return;
        }
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            try (Statement init = conn.createStatement()) {
                init.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_id TEXT, status TEXT, updated_at INTEGER, raw_json TEXT)");
                init.execute("CREATE TABLE IF NOT EXISTS event_cursors (run_id TEXT PRIMARY KEY, cursor INTEGER, updated_at INTEGER)");
            }
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM event_cursors WHERE run_id IN (SELECT run_id FROM runs WHERE plan_id=?)")) {
                stmt.setString(1, planId);
                stmt.executeUpdate();
            }
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM runs WHERE plan_id=?")) {
                stmt.setString(1, planId);
                stmt.executeUpdate();
            }
        }
    }
}
