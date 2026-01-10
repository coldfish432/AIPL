package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.service.WorkspaceService;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/workspace")
public class WorkspaceController {
    private final WorkspaceService workspaceService;

    public WorkspaceController(WorkspaceService workspaceService) {
        this.workspaceService = workspaceService;
    }

    @GetMapping("/info")
    public ApiResponse<JsonNode> info(@RequestParam String workspace) throws Exception {
        if (workspace == null || workspace.isBlank()) {
            return ApiResponse.fail("workspace is required");
        }
        JsonNode data = workspaceService.describeWorkspace(workspace);
        return ApiResponse.ok(data);
    }
}
