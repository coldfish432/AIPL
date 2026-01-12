package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.engine.EngineClient;
import com.aipl.platform.service.WorkspaceService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.file.Files;
import java.nio.file.Path;

@RestController
@RequestMapping("/api/workspace")
public class WorkspaceController {
    private final WorkspaceService workspaceService;
    private final EngineClient engineClient;
    private final ObjectMapper mapper = new ObjectMapper();

    public WorkspaceController(WorkspaceService workspaceService, EngineClient engineClient) {
        this.workspaceService = workspaceService;
        this.engineClient = engineClient;
    }

    /**
     * 获取工作区详细信息
     */
    @GetMapping("/info")
    public ApiResponse<JsonNode> info(@RequestParam String workspace) throws Exception {
        if (workspace == null || workspace.isBlank()) {
            return ApiResponse.fail("workspace is required");
        }
        JsonNode data = workspaceService.describeWorkspace(workspace);
        return ApiResponse.ok(data);
    }

    /**
     * 检测工作区路径是否有效
     * 返回错误代码供前端翻译：
     * - PATH_NOT_FOUND: 路径不存在
     * - NOT_A_DIRECTORY: 路径不是目录
     */
    @GetMapping("/detect")
    public ApiResponse<JsonNode> detect(@RequestParam String workspace) {
        if (workspace == null || workspace.isBlank()) {
            return ApiResponse.fail("workspace is required");
        }

        Path path = Path.of(workspace);
        ObjectNode result = mapper.createObjectNode();

        if (!Files.exists(path)) {
            result.put("exists", false);
            result.put("valid", false);
            result.put("reason", "PATH_NOT_FOUND");
            return ApiResponse.ok(result);
        }

        if (!Files.isDirectory(path)) {
            result.put("exists", true);
            result.put("valid", false);
            result.put("reason", "NOT_A_DIRECTORY");
            return ApiResponse.ok(result);
        }

        result.put("exists", true);
        result.put("valid", true);
        result.put("path", path.toAbsolutePath().toString());
        result.put("name", path.getFileName() != null ? path.getFileName().toString() : workspace);

        return ApiResponse.ok(result);
    }

    /**
     * 获取工作区目录树
     */
    @GetMapping("/tree")
    public ApiResponse<JsonNode> tree(
            @RequestParam String workspace,
            @RequestParam(defaultValue = "3") int depth
    ) {
        if (workspace == null || workspace.isBlank()) {
            return ApiResponse.fail("workspace is required");
        }

        try {
            JsonNode data = engineClient.workspaceTree(workspace, depth);
            return ApiResponse.ok(data);
        } catch (Exception e) {
            return ApiResponse.fail("Failed to get workspace tree: " + e.getMessage());
        }
    }

    /**
     * 读取工作区文件内容
     */
    @GetMapping("/read")
    public ApiResponse<JsonNode> read(
            @RequestParam String workspace,
            @RequestParam String path
    ) {
        if (workspace == null || workspace.isBlank()) {
            return ApiResponse.fail("workspace is required");
        }
        if (path == null || path.isBlank()) {
            return ApiResponse.fail("path is required");
        }

        try {
            JsonNode data = engineClient.workspaceRead(workspace, path);
            return ApiResponse.ok(data);
        } catch (Exception e) {
            return ApiResponse.fail("Failed to read file: " + e.getMessage());
        }
    }
}
