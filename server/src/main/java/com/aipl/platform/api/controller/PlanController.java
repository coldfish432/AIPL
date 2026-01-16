package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.AssistantChatRequest;
import com.aipl.platform.api.dto.request.AssistantPlanRequest;
import com.aipl.platform.api.dto.request.PlanRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.service.AssistantService;
import com.aipl.platform.service.PlanService;
import com.aipl.platform.service.RunService;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class PlanController {
    private final PlanService planService;
    private final AssistantService assistantService;
    private final RunService runService;

    public PlanController(PlanService planService, AssistantService assistantService, RunService runService) {
        this.planService = planService;
        this.assistantService = assistantService;
        this.runService = runService;
    }

    @PostMapping("/plans")
    public ApiResponse<JsonNode> plan(@RequestBody PlanRequest req) throws Exception {
        JsonNode res = planService.plan(req.task, req.planId, req.workspace);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/assistant/chat")
    public ApiResponse<JsonNode> assistantChat(@RequestBody AssistantChatRequest req) throws Exception {
        JsonNode res = assistantService.chat(req.messages, req.message, req.workspace);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/assistant/plan")
    public ApiResponse<JsonNode> assistantPlan(@RequestBody AssistantPlanRequest req) throws Exception {
        String task = assistantService.buildTaskFromMessages(req.messages);
        JsonNode res = planService.plan(task, req.planId, req.workspace);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @GetMapping("/plans")
    public ApiResponse<List<JsonNode>> listPlans(@RequestParam(required = false) String workspace) throws Exception {
        return ApiResponse.ok(planService.listPlans(workspace));
    }

    @GetMapping("/plans/{planId}")
    public ApiResponse<JsonNode> planDetail(@PathVariable String planId) throws Exception {
        return ApiResponse.ok(planService.planDetail(planId));
    }

    /**
     * Starts a run for an existing plan.
     */
    @PostMapping("/plans/{planId}/run")
    public ApiResponse<JsonNode> runPlan(
            @PathVariable String planId,
            @RequestBody(required = false) Map<String, String> body
    ) throws Exception {
        String workspace = body != null ? body.get("workspace") : null;
        String mode = body != null ? body.get("mode") : null;
        if (mode == null || mode.isBlank()) {
            mode = "autopilot";
        }

        JsonNode res = runService.runPlan(planId, workspace, mode);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/plans/{planId}/rework")
    public ApiResponse<JsonNode> reworkPlan(@PathVariable String planId) throws Exception {
        JsonNode res = runService.reworkPlan(planId);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @DeleteMapping("/plans/{planId}")
    public ApiResponse<JsonNode> deletePlan(@PathVariable String planId) throws Exception {
        return ApiResponse.ok(planService.deletePlan(planId));
    }
}
