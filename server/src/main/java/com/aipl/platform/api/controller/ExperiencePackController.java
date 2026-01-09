package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.CheckRequest;
import com.aipl.platform.api.dto.request.ExperiencePackExportRequest;
import com.aipl.platform.api.dto.request.ExperiencePackImportRequest;
import com.aipl.platform.api.dto.request.ExperiencePackImportWorkspaceRequest;
import com.aipl.platform.api.dto.request.RuleRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.service.ExperiencePackService;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/workspaces/{workspaceId}")
public class ExperiencePackController {
    private final ExperiencePackService service;

    public ExperiencePackController(ExperiencePackService service) {
        this.service = service;
    }

    @GetMapping("/memory")
    public ApiResponse<JsonNode> memory(@PathVariable String workspaceId) throws Exception {
        return ApiResponse.ok(service.memory(workspaceId));
    }

    @GetMapping("/experience-packs")
    public ApiResponse<JsonNode> list(@PathVariable String workspaceId) throws Exception {
        return ApiResponse.ok(service.list(workspaceId));
    }

    @GetMapping("/experience-packs/{packId}")
    public ApiResponse<JsonNode> get(@PathVariable String workspaceId, @PathVariable String packId) throws Exception {
        return ApiResponse.ok(service.get(workspaceId, packId));
    }

    @PostMapping("/experience-packs/import")
    public ApiResponse<JsonNode> importPack(@PathVariable String workspaceId, @RequestBody ExperiencePackImportRequest req) throws Exception {
        return ApiResponse.ok(service.importPack(workspaceId, req.pack));
    }

    @PostMapping("/experience-packs/import-workspace")
    public ApiResponse<JsonNode> importWorkspace(@PathVariable String workspaceId, @RequestBody ExperiencePackImportWorkspaceRequest req) throws Exception {
        return ApiResponse.ok(service.importWorkspace(
                workspaceId,
                req.fromWorkspaceId,
                req.includeRules,
                req.includeChecks,
                req.includeLessons,
                req.includePatterns
        ));
    }

    @PostMapping("/experience-packs/export")
    public ApiResponse<JsonNode> exportPack(@PathVariable String workspaceId, @RequestBody ExperiencePackExportRequest req) throws Exception {
        return ApiResponse.ok(service.exportPack(
                workspaceId,
                req.name,
                req.description,
                req.includeRules,
                req.includeChecks,
                req.includeLessons,
                req.includePatterns
        ));
    }

    @DeleteMapping("/experience-packs/{packId}")
    public ApiResponse<JsonNode> delete(@PathVariable String workspaceId, @PathVariable String packId) throws Exception {
        return ApiResponse.ok(service.delete(workspaceId, packId));
    }

    @PatchMapping("/experience-packs/{packId}")
    public ApiResponse<JsonNode> update(@PathVariable String workspaceId, @PathVariable String packId, @RequestBody JsonNode req) throws Exception {
        Boolean enabled = req.has("enabled") ? req.get("enabled").asBoolean() : null;
        return ApiResponse.ok(service.update(workspaceId, packId, enabled));
    }

    @PostMapping("/rules")
    public ApiResponse<JsonNode> addRule(@PathVariable String workspaceId, @RequestBody RuleRequest req) throws Exception {
        return ApiResponse.ok(service.addRule(workspaceId, req.content, req.scope, req.category));
    }

    @DeleteMapping("/rules/{ruleId}")
    public ApiResponse<JsonNode> deleteRule(@PathVariable String workspaceId, @PathVariable String ruleId) throws Exception {
        return ApiResponse.ok(service.deleteRule(workspaceId, ruleId));
    }

    @PostMapping("/checks")
    public ApiResponse<JsonNode> addCheck(@PathVariable String workspaceId, @RequestBody CheckRequest req) throws Exception {
        return ApiResponse.ok(service.addCheck(workspaceId, req.check, req.scope));
    }

    @DeleteMapping("/checks/{checkId}")
    public ApiResponse<JsonNode> deleteCheck(@PathVariable String workspaceId, @PathVariable String checkId) throws Exception {
        return ApiResponse.ok(service.deleteCheck(workspaceId, checkId));
    }

    @DeleteMapping("/lessons/{lessonId}")
    public ApiResponse<JsonNode> deleteLesson(@PathVariable String workspaceId, @PathVariable String lessonId) throws Exception {
        return ApiResponse.ok(service.deleteLesson(workspaceId, lessonId));
    }

    @DeleteMapping("/lessons")
    public ApiResponse<JsonNode> clearLessons(@PathVariable String workspaceId) throws Exception {
        return ApiResponse.ok(service.clearLessons(workspaceId));
    }
}
