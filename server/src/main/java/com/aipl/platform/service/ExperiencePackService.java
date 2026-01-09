package com.aipl.platform.service;

import com.aipl.platform.engine.EngineClient;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;

@Service
public class ExperiencePackService {
    private final EngineClient engine;

    public ExperiencePackService(EngineClient engine) {
        this.engine = engine;
    }

    public JsonNode memory(String workspaceId) throws Exception {
        return engine.memory(workspaceId);
    }

    public JsonNode list(String workspaceId) throws Exception {
        return engine.experiencePacks("list", workspaceId, null, null, null, null, null, null, null, null, null, null);
    }

    public JsonNode get(String workspaceId, String packId) throws Exception {
        return engine.experiencePacks("get", workspaceId, packId, null, null, null, null, null, null, null, null, null);
    }

    public JsonNode importPack(String workspaceId, JsonNode pack) throws Exception {
        return engine.experiencePacks("import", workspaceId, null, pack, null, null, null, null, null, null, null, null);
    }

    public JsonNode importWorkspace(String workspaceId, String fromWorkspaceId, Boolean includeRules, Boolean includeChecks, Boolean includeLessons, Boolean includePatterns) throws Exception {
        return engine.experiencePacks("import-workspace", workspaceId, null, null, fromWorkspaceId, includeRules, includeChecks, includeLessons, includePatterns, null, null, null);
    }

    public JsonNode exportPack(String workspaceId, String name, String description, Boolean includeRules, Boolean includeChecks, Boolean includeLessons, Boolean includePatterns) throws Exception {
        return engine.experiencePacks("export", workspaceId, null, null, null, includeRules, includeChecks, includeLessons, includePatterns, name, description, null);
    }

    public JsonNode delete(String workspaceId, String packId) throws Exception {
        return engine.experiencePacks("delete", workspaceId, packId, null, null, null, null, null, null, null, null, null);
    }

    public JsonNode update(String workspaceId, String packId, Boolean enabled) throws Exception {
        return engine.experiencePacks("update", workspaceId, packId, null, null, null, null, null, null, null, null, enabled);
    }

    public JsonNode addRule(String workspaceId, String content, String scope, String category) throws Exception {
        return engine.rules("add", workspaceId, null, content, scope, category);
    }

    public JsonNode deleteRule(String workspaceId, String ruleId) throws Exception {
        return engine.rules("delete", workspaceId, ruleId, null, null, null);
    }

    public JsonNode addCheck(String workspaceId, JsonNode check, String scope) throws Exception {
        return engine.checks("add", workspaceId, null, check, scope);
    }

    public JsonNode deleteCheck(String workspaceId, String checkId) throws Exception {
        return engine.checks("delete", workspaceId, checkId, null, null);
    }

    public JsonNode deleteLesson(String workspaceId, String lessonId) throws Exception {
        return engine.lessons("delete", workspaceId, lessonId);
    }

    public JsonNode clearLessons(String workspaceId) throws Exception {
        return engine.lessons("clear", workspaceId, null);
    }
}
