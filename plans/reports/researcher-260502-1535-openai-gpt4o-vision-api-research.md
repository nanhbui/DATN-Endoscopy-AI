# OpenAI GPT-4o Vision API Research Report

**Date:** May 2, 2026  
**Scope:** Endoscopy AI system integration with OpenAI APIs

---

## Q1: GPT-4o Vision API Format (Base64 + Streaming)

**Messages array format:**
```json
{
  "model": "gpt-4o",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Your prompt here"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,{BASE64_STRING}",
            "detail": "low"
          }
        }
      ]
    }
  ],
  "stream": true
}
```

**Async Python implementation:**
```python
from openai import AsyncOpenAI

client = AsyncOpenAI()
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Analyze this endoscopy image"},
            {"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{base64_string}",
                "detail": "low"
            }}
        ]
    }],
    stream=True
)
```

**Key detail:** Replace `{BASE64_STRING}` with your pre-encoded JPEG base64 string. Image tokens: 85 base + 170 per tile.

---

## Q2: Conversation History with Hybrid Vision/Text

**Image context retention:** GPT-4o retains image context within the same conversation. Follow-up messages can be text-only.

**Pattern:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,...", "detail": "low"}},
        {"type": "text", "text": "Initial prompt with image"}
      ]
    },
    {"role": "assistant", "content": "Response to image analysis"},
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Follow-up question about the image"}
      ]
    }
  ]
}
```

**Behavior:** Model implicitly references the image from turn 1 in turn 3. No need to re-send the image. Context window shared across all turns.

---

## Q3: OpenAI Prompt Caching Details

| Parameter | Value |
|-----------|-------|
| **Min tokens for cache** | 1,024 tokens |
| **Cache increments** | 128 tokens |
| **TTL (in-memory)** | 5-10 min (max 1 hour) |
| **Extended TTL** | Up to 24 hours |
| **GPT-4o support** | Yes, full support |
| **Discount rate** | 50% off cached input tokens |
| **Cost** | $1.25/M cached tokens (vs $2.50/M normal) |

**Mechanism:** Cached tokens don't incur fee reduction, but do reduce latency. First call pays full price; subsequent calls within TTL pay 50% for cached portion.

---

## Q4: Cost Comparison (May 2026 Pricing)

**Current Baseline (GPT-4o-mini text):**
- Input: 200 tokens × $0.15/1M = $0.000030
- Output: 400 tokens × $0.60/1M = $0.000240
- **Per call: $0.00027** (negligible)

**Proposed Initial Call (GPT-4o vision + system prompt):**
- Image tokens: 85 × $2.50/1M = $0.0002125
- System tokens: 1,500 × $2.50/1M = $0.00375
- User tokens: 100 × $2.50/1M = $0.00025
- Output: 700 × $10.00/1M = $0.007
- **Per initial call: $0.011** (40x baseline)

**Proposed Follow-up (GPT-4o-mini text):**
- Context: 1,700 tokens × $0.15/1M = $0.000255
- User: 200 tokens × $0.15/1M = $0.00003
- Output: 300 tokens × $0.60/1M = $0.00018
- **Per follow-up: $0.000285** (0.3x baseline, negligible)

**Pattern per endoscopy analysis:** 1 vision call + N text follow-ups = $0.011 + (N × $0.0003).

**With prompt caching (if system prompt >1024 tokens):** Subsequent analyses after first call cache system prompt → save $0.00375 per initial call (34% reduction in vision call cost).

---

## Summary

- **Vision format:** Base64 JPEG in `data:image/jpeg;base64,{string}` with `detail="low"`
- **Conversation:** Images persist; follow-ups are text-only
- **Caching:** 1024+ token threshold, 50% discount, 5-10 min default TTL
- **Costs:** Vision call ~$0.011, follow-ups ~$0.0003 (GPT-4o-mini)

**Recommendation:** Use vision for initial analysis; leverage text follow-ups for cost efficiency. System prompt caching yields 34% reduction on repeat analyses.

---

## Sources
- [OpenAI Images & Vision API](https://developers.openai.com/api/docs/guides/images-vision)
- [OpenAI Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [OpenAI Pricing (May 2026)](https://developers.openai.com/api/docs/pricing)
- [GPT-4o Vision Guide](https://getstream.io/blog/gpt-4o-vision-guide/)
- [Conversation State Documentation](https://developers.openai.com/api/docs/guides/conversation-state)
