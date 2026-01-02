package com.aipl.platform.api.exception;

import com.aipl.platform.api.dto.response.ApiResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BusinessException.class)
    public ApiResponse<String> handleBusiness(BusinessException ex) {
        return ApiResponse.fail(ex.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public ApiResponse<String> handleGeneric(Exception ex) {
        log.error("Unhandled exception", ex);
        String message = ex.getMessage();
        if (message == null || message.isBlank()) {
            message = "internal_error";
        }
        return ApiResponse.fail(message);
    }
}
