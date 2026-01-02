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

@Component
public class PlanRepository {
    private final Path dbPath;
    private final ObjectMapper mapper = new ObjectMapper();

    public PlanRepository(@Value("${app.dbPath}") String dbPath) {
        this.dbPath = Path.of(dbPath).toAbsolutePath();
    }

    public List<JsonNode> listPlansFromDb() throws Exception {
        if (dbPath == null || !Files.exists(dbPath)) {
            return List.of();
        }
        List<JsonNode> items = new ArrayList<>();
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            try (Statement init = conn.createStatement()) {
                init.execute("CREATE TABLE IF NOT EXISTS plans (plan_id TEXT PRIMARY KEY, updated_at INTEGER, raw_json TEXT)");
            }
            try (PreparedStatement stmt = conn.prepareStatement("SELECT plan_id, updated_at, raw_json FROM plans ORDER BY updated_at DESC");
                 ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    String planId = rs.getString("plan_id");
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
                    if (!node.has("plan_id") && planId != null) {
                        node.put("plan_id", planId);
                    }
                    node.put("updated_at", updatedAt);
                    items.add(node);
                }
            }
        }
        return items;
    }

    public void deletePlan(String planId) throws Exception {
        if (planId == null || planId.isBlank() || dbPath == null) {
            return;
        }
        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + dbPath)) {
            try (Statement init = conn.createStatement()) {
                init.execute("CREATE TABLE IF NOT EXISTS plans (plan_id TEXT PRIMARY KEY, updated_at INTEGER, raw_json TEXT)");
            }
            try (PreparedStatement stmt = conn.prepareStatement("DELETE FROM plans WHERE plan_id=?")) {
                stmt.setString(1, planId);
                stmt.executeUpdate();
            }
        }
    }
}
