package com.aipl.platform.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

@Component
public class ApiKeyFilter extends OncePerRequestFilter {
    private final Set<String> keys;

    public ApiKeyFilter(@Value("${AIPL_API_KEYS:}") String rawKeys) {
        if (rawKeys == null || rawKeys.isBlank()) {
            this.keys = new HashSet<>();
        } else {
            this.keys = new HashSet<>(Arrays.asList(rawKeys.split(",")));
        }
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        if (!keys.isEmpty()) {
            String key = request.getHeader("X-API-Key");
            if (key == null || !keys.contains(key)) {
                response.setStatus(401);
                response.getWriter().write("unauthorized");
                return;
            }
        } else {
            String addr = request.getRemoteAddr();
            if (!("127.0.0.1".equals(addr) || "::1".equals(addr))) {
                response.setStatus(403);
                response.getWriter().write("forbidden");
                return;
            }
        }
        filterChain.doFilter(request, response);
    }
}
