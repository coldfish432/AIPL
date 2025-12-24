package com.aipl.platform.store;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

@Component
public class RunStore {
    private final ConcurrentMap<String, Integer> cursors = new ConcurrentHashMap<>();

    public RunStore(@Value("${app.dbPath}") String dbPath) {
        // dbPath reserved for Python mirror; Java no longer writes to SQLite.
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
}
