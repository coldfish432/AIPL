package com.aipl.platform.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

public final class JsonCaseHelper {
    private JsonCaseHelper() {
    }

    public static void copyValue(ObjectNode node, String source, String target) {
        if (node == null || target == null || node.has(target)) {
            return;
        }
        JsonNode value = node.get(source);
        if (value != null) {
            node.set(target, value);
        }
    }

    public static void ensurePlanFields(ObjectNode node) {
        if (node == null) {
            return;
        }
        copyValue(node, "plan_id", "planId");
        copyValue(node, "tasks_count", "tasksCount");
        copyValue(node, "created_at", "createdAt");
        copyValue(node, "updated_at", "updatedAt");
        copyValue(node, "workspace_path", "workspacePath");
        copyValue(node, "task_chain_text", "taskChainText");
        copyValue(node, "input_task", "inputTask");
    }

    public static void ensureRunFields(ObjectNode node) {
        if (node == null) {
            return;
        }
        copyValue(node, "run_id", "runId");
        copyValue(node, "plan_id", "planId");
        copyValue(node, "input_task", "inputTask");
        copyValue(node, "patchset_path", "patchsetPath");
        copyValue(node, "changed_files_count", "changedFilesCount");
        copyValue(node, "workspace_main_root", "workspaceMainRoot");
        copyValue(node, "workspace_stage_root", "workspaceStageRoot");
        copyValue(node, "created_at", "createdAt");
        copyValue(node, "updated_at", "updatedAt");
    }

    public static String getPlanId(JsonNode node) {
        return getFirstText(node, "planId", "plan_id", "id");
    }

    public static String getRunId(JsonNode node) {
        return getFirstText(node, "runId", "run_id", "id");
    }

    private static String getFirstText(JsonNode node, String... keys) {
        if (node == null) {
            return null;
        }
        for (String key : keys) {
            JsonNode value = node.get(key);
            if (value != null && value.isTextual()) {
                String text = value.asText();
                if (!isBlank(text)) {
                    return text;
                }
            }
        }
        return null;
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
