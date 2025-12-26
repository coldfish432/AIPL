package com.aipl.platform.api.dto.response;

import java.time.Instant;
import java.util.UUID;

public class ApiResponse<T> {
    public String request_id;
    public boolean ok;
    public long ts;
    public T data;
    public String error;

    public static <T> ApiResponse<T> ok(T data) {
        ApiResponse<T> res = new ApiResponse<>();
        res.request_id = "req_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        res.ok = true;
        res.ts = Instant.now().getEpochSecond();
        res.data = data;
        res.error = null;
        return res;
    }

    public static <T> ApiResponse<T> fail(String error) {
        ApiResponse<T> res = new ApiResponse<>();
        res.request_id = "req_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        res.ok = false;
        res.ts = Instant.now().getEpochSecond();
        res.data = null;
        res.error = error;
        return res;
    }
}
