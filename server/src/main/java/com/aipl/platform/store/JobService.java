package com.aipl.platform.store;

import com.aipl.platform.engine.EngineClient;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.sql.*;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Component
public class JobService {
    private final EngineClient engine;
    private final String dbUrl;
    private final int maxWorkers;

    public JobService(EngineClient engine, @Value("${app.dbPath}") String dbPath,
                      @Value("${app.maxWorkers:2}") int maxWorkers) throws Exception {
        this.engine = engine;
        java.nio.file.Path p = java.nio.file.Path.of(dbPath).toAbsolutePath();
        if (p.getParent() != null) {
            java.nio.file.Files.createDirectories(p.getParent());
        }
        this.dbUrl = "jdbc:sqlite:" + p;
        this.maxWorkers = Math.max(1, maxWorkers);
        init();
    }

    private void init() throws Exception {
        try (Connection conn = DriverManager.getConnection(dbUrl);
             Statement st = conn.createStatement()) {
            st.executeUpdate("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, plan_id TEXT, run_id TEXT, goal TEXT, workspace TEXT, status TEXT, created_at INTEGER, updated_at INTEGER)");
        }
    }

    @PostConstruct
    public void startWorkers() {
        for (int i = 0; i < maxWorkers; i++) {
            Thread t = new Thread(this::workerLoop, "job-worker-" + i);
            t.setDaemon(true);
            t.start();
        }
    }

    public String enqueue(String task, String planId, String workspace) throws Exception {
        String jobId = "job_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        long now = Instant.now().getEpochSecond();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("INSERT INTO jobs(job_id, plan_id, run_id, goal, workspace, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)")) {
            ps.setString(1, jobId);
            ps.setString(2, planId);
            ps.setString(3, null);
            ps.setString(4, task);
            ps.setString(5, workspace);
            ps.setString(6, "queued");
            ps.setLong(7, now);
            ps.setLong(8, now);
            ps.executeUpdate();
        }
        return jobId;
    }

    public List<JsonNode> listJobs(com.fasterxml.jackson.databind.ObjectMapper mapper) throws Exception {
        List<JsonNode> items = new ArrayList<>();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("SELECT job_id, plan_id, run_id, goal, workspace, status, created_at, updated_at FROM jobs ORDER BY created_at DESC")) {
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                ObjectNode node = mapper.createObjectNode();
                node.put("job_id", rs.getString(1));
                node.put("plan_id", rs.getString(2));
                node.put("run_id", rs.getString(3));
                node.put("task", rs.getString(4));
                node.put("workspace", rs.getString(5));
                node.put("status", rs.getString(6));
                node.put("created_at", rs.getLong(7));
                node.put("updated_at", rs.getLong(8));
                items.add(node);
            }
        }
        return items;
    }

    public void cancel(String jobId) throws Exception {
        long now = Instant.now().getEpochSecond();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("UPDATE jobs SET status='canceled', updated_at=? WHERE job_id=?")) {
            ps.setLong(1, now);
            ps.setString(2, jobId);
            ps.executeUpdate();
        }
    }

    private void workerLoop() {
        while (true) {
            try {
                String jobId = null;
                String task = null;
                String planId = null;
                String workspace = null;
                try (Connection conn = DriverManager.getConnection(dbUrl);
                     PreparedStatement ps = conn.prepareStatement("SELECT job_id, goal, plan_id, workspace FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1")) {
                    ResultSet rs = ps.executeQuery();
                    if (rs.next()) {
                        jobId = rs.getString(1);
                        task = rs.getString(2);
                        planId = rs.getString(3);
                        workspace = rs.getString(4);
                    }
                }
                if (jobId == null) {
                    Thread.sleep(1000);
                    continue;
                }
                long now = Instant.now().getEpochSecond();
                try (Connection conn = DriverManager.getConnection(dbUrl);
                     PreparedStatement ps = conn.prepareStatement("UPDATE jobs SET status='running', updated_at=? WHERE job_id=?")) {
                    ps.setLong(1, now);
                    ps.setString(2, jobId);
                    ps.executeUpdate();
                }

                JsonNode res = engine.run(task, planId, workspace);
                JsonNode data = res.get("data");
                String runId = data != null && data.has("run_id") ? data.get("run_id").asText() : null;
                String status = data != null && data.has("status") ? data.get("status").asText() : null;

                try (Connection conn = DriverManager.getConnection(dbUrl);
                     PreparedStatement ps = conn.prepareStatement("UPDATE jobs SET status=?, run_id=?, updated_at=? WHERE job_id=?")) {
                    ps.setString(1, status != null ? status : "done");
                    ps.setString(2, runId);
                    ps.setLong(3, Instant.now().getEpochSecond());
                    ps.setString(4, jobId);
                    ps.executeUpdate();
                }
            } catch (Exception e) {
                // swallow to keep worker alive
                try { Thread.sleep(1000); } catch (InterruptedException ignored) {}
            }
        }
    }
}
