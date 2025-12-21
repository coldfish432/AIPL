package com.aipl.platform.store;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.Statement;
import java.nio.file.Path;

@Component
public class RunStore {
    private final String dbUrl;

    public RunStore(@Value("${app.dbPath}") String dbPath) throws Exception {
        Path p = Path.of(dbPath).toAbsolutePath();
        if (p.getParent() != null) {
            java.nio.file.Files.createDirectories(p.getParent());
        }
        this.dbUrl = "jdbc:sqlite:" + p.toString();
        init();
    }

    private void init() throws Exception {
        try (Connection conn = DriverManager.getConnection(dbUrl);
             Statement st = conn.createStatement()) {
            st.executeUpdate("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_id TEXT, status TEXT, updated_at INTEGER, raw_json TEXT)");
            st.executeUpdate("CREATE TABLE IF NOT EXISTS plans (plan_id TEXT PRIMARY KEY, updated_at INTEGER, raw_json TEXT)");
            st.executeUpdate("CREATE TABLE IF NOT EXISTS event_cursors (run_id TEXT PRIMARY KEY, cursor INTEGER, updated_at INTEGER)");
        }
    }

    public void upsertRun(JsonNode res) throws Exception {
        JsonNode data = res.get("data");
        if (data == null) return;
        String runId = data.has("run_id") ? data.get("run_id").asText() : null;
        if (runId == null || runId.isBlank()) return;
        String planId = data.has("plan_id") ? data.get("plan_id").asText() : null;
        String status = data.has("status") ? data.get("status").asText() : null;
        long now = System.currentTimeMillis();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("INSERT INTO runs(run_id, plan_id, status, updated_at, raw_json) VALUES(?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET plan_id=excluded.plan_id, status=excluded.status, updated_at=excluded.updated_at, raw_json=excluded.raw_json")) {
            ps.setString(1, runId);
            ps.setString(2, planId);
            ps.setString(3, status);
            ps.setLong(4, now);
            ps.setString(5, res.toString());
            ps.executeUpdate();
        }
    }


    public int getCursor(String runId) throws Exception {
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("SELECT cursor FROM event_cursors WHERE run_id=?")) {
            ps.setString(1, runId);
            var rs = ps.executeQuery();
            if (rs.next()) {
                return rs.getInt(1);
            }
        }
        return 0;
    }

    public void setCursor(String runId, int cursor) throws Exception {
        long now = System.currentTimeMillis();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("INSERT INTO event_cursors(run_id, cursor, updated_at) VALUES(?,?,?) ON CONFLICT(run_id) DO UPDATE SET cursor=excluded.cursor, updated_at=excluded.updated_at")) {
            ps.setString(1, runId);
            ps.setInt(2, cursor);
            ps.setLong(3, now);
            ps.executeUpdate();
        }
    }

    public void upsertPlan(JsonNode res) throws Exception {
        JsonNode data = res.get("data");
        if (data == null) return;
        String planId = data.has("plan_id") ? data.get("plan_id").asText() : null;
        if (planId == null || planId.isBlank()) return;
        long now = System.currentTimeMillis();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("INSERT INTO plans(plan_id, updated_at, raw_json) VALUES(?,?,?) ON CONFLICT(plan_id) DO UPDATE SET updated_at=excluded.updated_at, raw_json=excluded.raw_json")) {
            ps.setString(1, planId);
            ps.setLong(2, now);
            ps.setString(3, res.toString());
            ps.executeUpdate();
        }
    }
}
