## Optimization Summary - Gemini Models

### Performance Comparison (Latency)
```
Model                    Speed       Quality      Use Case
─────────────────────────────────────────────────────────────
Gemini 2.5 Flash Lite   0.6-1s      Good         ✅ Default, Chat
Gemini 2.5 Flash        7-9s        Better       Complex queries
Gemini 2.5 Pro          15-18s      Best         High-quality
Grok 2                  3-5s        Good         Alternative
```

### Optimizations Applied

1. **REST API with Streaming Support**
   - Direct HTTP calls to Gemini API
   - SSE (Server-Sent Events) streaming for faster perceived response
   - Reduced timeout: 30s → 15s

2. **Default Model: Flash Lite**
   - Fastest response time (~0.7s avg)
   - Good enough quality for 90% of chat queries
   - User can switch to Pro/Flash for complex tasks

3. **Caching Strategy** (Future)
   - Consider caching common queries
   - Use Redis for session/context caching
   - Implement rate limiting per user

4. **Model Selection Tips**
   - **Flash Lite**: Quick answers, casual chat, simple Q&A
   - **Flash**: Code generation, medium complexity
   - **Pro**: Creative writing, complex reasoning, analysis
   - **Grok**: Alternative when Gemini is slow

### Current Configuration
```python
# Backend default
model_key = data.get("model", "gemini-flash-lite")

# Frontend default
<div class="selected">Gemini 2.5 Flash Lite ⚡</div>

# Available models
models = {
    "gemini-flash-lite": GeminiAPIWrapper("gemini-2.5-flash-lite", ...),
    "gemini-flash": GeminiAPIWrapper("gemini-2.5-flash", ...),
    "gemini-pro": GeminiAPIWrapper("gemini-2.5-pro", ...),
    "grok-2": grok_chat,
}
```

### Response Time Goals
- ✅ Simple Q&A: < 1s
- ✅ Medium queries: < 3s
- ✅ Complex tasks: < 10s
- ⚠️  Very complex: < 20s

### Monitoring
Check logs:
```bash
tail -f /home/chatbotD8ZL/chatbot.toila.ai.vn/logs/gunicorn_access.log
```

Look for response times in microseconds (last number).
