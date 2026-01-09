package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.LanguagePackExportRequest;
import com.aipl.platform.api.dto.request.LanguagePackImportRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.service.LanguagePackService;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/language-packs")
public class LanguagePackController {
    private final LanguagePackService service;

    public LanguagePackController(LanguagePackService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<JsonNode> list(@RequestParam(required = false) String workspace) throws Exception {
        return ApiResponse.ok(service.list(workspace));
    }

    @GetMapping("/{packId}")
    public ApiResponse<JsonNode> get(@PathVariable String packId) throws Exception {
        return ApiResponse.ok(service.get(packId));
    }

    @PostMapping("/import")
    public ApiResponse<JsonNode> importPack(@RequestBody LanguagePackImportRequest req) throws Exception {
        return ApiResponse.ok(service.importPack(req.pack));
    }

    @GetMapping("/{packId}/export")
    public ApiResponse<JsonNode> exportPack(@PathVariable String packId) throws Exception {
        return ApiResponse.ok(service.export(packId));
    }

    @PostMapping("/learned/export")
    public ApiResponse<JsonNode> exportLearned(@RequestBody LanguagePackExportRequest req) throws Exception {
        return ApiResponse.ok(service.exportLearned(req.name, req.description));
    }

    @PostMapping("/{packId}/export-merged")
    public ApiResponse<JsonNode> exportMerged(@PathVariable String packId, @RequestBody LanguagePackExportRequest req) throws Exception {
        return ApiResponse.ok(service.exportMerged(packId, req.name, req.description));
    }

    @DeleteMapping("/{packId}")
    public ApiResponse<JsonNode> delete(@PathVariable String packId) throws Exception {
        return ApiResponse.ok(service.delete(packId));
    }

    @PatchMapping("/{packId}")
    public ApiResponse<JsonNode> update(@PathVariable String packId, @RequestBody JsonNode req) throws Exception {
        Boolean enabled = req.has("enabled") ? req.get("enabled").asBoolean() : null;
        return ApiResponse.ok(service.update(packId, enabled));
    }

    @DeleteMapping("/learned")
    public ApiResponse<JsonNode> clearLearned() throws Exception {
        return ApiResponse.ok(service.clearLearned());
    }
}
