package com.aipl.platform.api.controller;

import com.aipl.platform.api.dto.request.AssistantChatRequest;
import com.aipl.platform.api.dto.request.AssistantPlanRequest;
import com.aipl.platform.api.dto.request.PlanRequest;
import com.aipl.platform.api.dto.response.ApiResponse;
import com.aipl.platform.service.AssistantService;
import com.aipl.platform.service.PlanService;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
public class PlanController {
    private final PlanService planService;
    private final AssistantService assistantService;

    public PlanController(PlanService planService, AssistantService assistantService) {
        this.planService = planService;
        this.assistantService = assistantService;
    }

    @PostMapping("/plans")
    public ApiResponse<JsonNode> plan(@RequestBody PlanRequest req) throws Exception {
        JsonNode res = planService.plan(req.task, req.planId, req.workspace);
        JsonNode data = res.has("data") ? res.get("data") : res;
        return ApiResponse.ok(data);
    }

    @PostMapping("/assistant/chat")
    public ApiResponse<JsonNode> assistantChat(@RequestBody AssistantChatRequest req) throws Exception {
        JsonNode res = assistantService.chat(req.messages, req.message);
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

    @DeleteMapping("/plans/{planId}")
    public ApiResponse<JsonNode> deletePlan(@PathVariable String planId) throws Exception {
        return ApiResponse.ok(planService.deletePlan(planId));
    }
}
