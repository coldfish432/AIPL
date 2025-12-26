package com.aipl.platform.repository;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Repository;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Repository
public class JobRepository {
    private final String dbUrl;

    public JobRepository(@Value("${app.dbPath}") String dbPath) throws Exception {
        java.nio.file.Path p = java.nio.file.Path.of(dbPath).toAbsolutePath();
        if (p.getParent() != null) {
            java.nio.file.Files.createDirectories(p.getParent());
        }
        this.dbUrl = "jdbc:sqlite:" + p;
        init();
    }

    private void init() throws Exception {
        try (Connection conn = DriverManager.getConnection(dbUrl);
             Statement st = conn.createStatement()) {
            st.executeUpdate("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, plan_id TEXT, run_id TEXT, goal TEXT, workspace TEXT, status TEXT, created_at INTEGER, updated_at INTEGER)");
        }
    }

    public void insertJob(String jobId, String task, String planId, String workspace, String status) throws Exception {
        long now = Instant.now().getEpochSecond();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("INSERT INTO jobs(job_id, plan_id, run_id, goal, workspace, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)")) {
            ps.setString(1, jobId);
            ps.setString(2, planId);
            ps.setString(3, null);
            ps.setString(4, task);
            ps.setString(5, workspace);
            ps.setString(6, status);
            ps.setLong(7, now);
            ps.setLong(8, now);
            ps.executeUpdate();
        }
    }

    public Optional<JobRecord> fetchNextQueued() throws Exception {
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("SELECT job_id, goal, plan_id, workspace FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1")) {
            ResultSet rs = ps.executeQuery();
            if (rs.next()) {
                return Optional.of(new JobRecord(
                        rs.getString(1),
                        rs.getString(2),
                        rs.getString(3),
                        rs.getString(4)
                ));
            }
        }
        return Optional.empty();
    }

    public void markRunning(String jobId) throws Exception {
        long now = Instant.now().getEpochSecond();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("UPDATE jobs SET status='running', updated_at=? WHERE job_id=?")) {
            ps.setLong(1, now);
            ps.setString(2, jobId);
            ps.executeUpdate();
        }
    }

    public void updateCompletion(String jobId, String status, String runId) throws Exception {
        long now = Instant.now().getEpochSecond();
        try (Connection conn = DriverManager.getConnection(dbUrl);
             PreparedStatement ps = conn.prepareStatement("UPDATE jobs SET status=?, run_id=?, updated_at=? WHERE job_id=?")) {
            ps.setString(1, status);
            ps.setString(2, runId);
            ps.setLong(3, now);
            ps.setString(4, jobId);
            ps.executeUpdate();
        }
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

    public List<JsonNode> listJobs(ObjectMapper mapper) throws Exception {
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

    public static class JobRecord {
        public final String jobId;
        public final String task;
        public final String planId;
        public final String workspace;

        public JobRecord(String jobId, String task, String planId, String workspace) {
            this.jobId = jobId;
            this.task = task;
            this.planId = planId;
            this.workspace = workspace;
        }
    }
}
