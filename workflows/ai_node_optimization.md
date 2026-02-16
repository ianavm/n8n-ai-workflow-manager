# AI Node Optimization SOP

## Objective
Optimize AI-specific nodes across n8n workflows for cost efficiency, prompt quality, model selection, and security. Position yourself as the AI expert managing the intelligence layer of your automation infrastructure.

## Prerequisites
- n8n API key configured
- Understanding of which workflows contain AI nodes
- Access to AI provider dashboards (OpenAI, Anthropic, OpenRouter) for cost verification

## Running an AI Audit

```bash
python tools/run_manager.py ai-audit
```

### What It Scans

The AI Node Manager detects these node types:

| Node Type | Category |
|-----------|----------|
| `lmChatOpenAi` | LangChain OpenAI chat models |
| `lmChatAnthropic` | LangChain Anthropic models |
| `agent` | LangChain AI agents |
| `chainLlm` | LangChain LLM chains |
| `chainSummarization` | Summarization chains |
| `memoryBufferWindow` | Conversation memory |
| `vectorStoreInMemory` | In-memory vector stores |
| `vectorStorePinecone` | Pinecone vector stores |
| `openAi` | Direct OpenAI API nodes |
| `httpRequest` | HTTP nodes calling AI APIs |
| `code` | Code nodes with AI SDK calls |

## Prompt Quality Analysis

The audit scores each prompt on 4 criteria (25 points each, 100 max):

| Criteria | What to Look For | Keywords Detected |
|----------|-------------------|-------------------|
| **Persona** | Clear role definition | "you are", "act as", "your role" |
| **Output Format** | Structured output instructions | "json", "format", "output" |
| **Examples** | Few-shot examples | "example", "e.g." |
| **Constraints** | Guardrails and boundaries | "do not", "never", "always", "must" |

### Improving Low-Scoring Prompts

**Score 0-25 (Poor):** Add all four elements. Start with persona and output format.

**Score 50 (Fair):** Add examples and constraints for consistency.

**Score 75-100 (Good):** Fine-tune for edge cases and test with varied inputs.

### Prompt Template for n8n AI Nodes

```
You are a [specific role] for [company/use case].

## Instructions
[Clear, specific instructions for the task]

## Output Format
Respond in JSON with these fields:
- field1: description
- field2: description

## Examples
Input: [example input]
Output: [example output]

## Constraints
- Do not [specific restriction]
- Always [required behavior]
- Maximum response length: [limit]
```

## Cost Optimization

### Model Cost Tiers (per 1K tokens)

| Model | Input Cost | Output Cost | Best For |
|-------|-----------|-------------|----------|
| GPT-4o | $0.005 | $0.015 | Complex reasoning, analysis |
| GPT-4o-mini | $0.00015 | $0.0006 | Simple classification, extraction |
| Claude 3 Sonnet | $0.003 | $0.015 | Balanced quality/cost |
| Claude 3 Haiku | $0.00025 | $0.00125 | High-volume, simple tasks |

### Cost Reduction Strategies

1. **Right-size your model:** Use GPT-4o-mini or Claude Haiku for simple tasks (classification, extraction, formatting). Reserve GPT-4o/Claude Sonnet for complex reasoning.

2. **Set max token limits:** Always configure `maxTokens` on every AI node. Prevents runaway costs from verbose responses.

3. **Optimize prompt length:** Shorter system prompts = lower input costs. Remove redundant instructions.

4. **Cache repeated queries:** If the same input produces the same output, cache results instead of re-calling the API.

5. **Batch processing:** Group multiple items into one API call where possible.

### Estimating Monthly Costs

The audit tool estimates costs based on:
- Prompt length (word count × 1.3 token estimate)
- Model cost tier
- Configured executions per day (default: 100)

Review `.tmp/ai_audit_results.json` → `cost_estimate` for breakdown.

## Model Selection Guide

| Use Case | Recommended Model | Why |
|----------|-------------------|-----|
| Lead qualification | GPT-4o-mini | Simple yes/no + score, high volume |
| Customer support | Claude Sonnet | Nuanced responses, good tone |
| Content generation | GPT-4o | Creative, high quality output |
| Data extraction | GPT-4o-mini | Structured output, fast |
| Summarization | Claude Haiku | Cost-effective, good enough quality |
| Agent/RAG pipelines | GPT-4o or Claude Sonnet | Needs strong reasoning |
| Translation | GPT-4o-mini | Simple task, fast |

## Security Audit

### Checks Performed

| Check | Severity | Issue |
|-------|----------|-------|
| No max token limit | Low | Unbounded API costs possible |
| Hardcoded API keys | High | Keys exposed in workflow JSON |
| No input sanitization | Medium | Prompt injection risk |
| User input in system prompt | Medium | Prompt manipulation possible |

### Security Best Practices

1. **Always set `maxTokens`** on every AI node (recommended: 500-2000 depending on use case)
2. **Use n8n credentials** for API keys, never hardcode in node parameters
3. **Sanitize user input** before passing to AI nodes - strip special characters, limit length
4. **Separate system and user prompts** - never concatenate user input into system messages
5. **Log AI responses** for audit trails on sensitive workflows

## Agent Architecture Patterns in n8n

### Pattern 1: Simple Chain
```
Trigger → AI Node → Output
```
Best for: One-shot tasks (classify, extract, summarize)

### Pattern 2: Agent with Tools
```
Trigger → LangChain Agent → [Tool 1, Tool 2, Tool 3] → Output
```
Best for: Multi-step reasoning, data lookup, calculations

### Pattern 3: RAG Pipeline
```
Trigger → Embedding → Vector Search → LLM with Context → Output
```
Best for: Knowledge-base Q&A, document search

### Pattern 4: Human-in-the-Loop
```
Trigger → AI Classification → IF (confidence > threshold) → Auto-respond
                              → ELSE → Queue for Human Review
```
Best for: Customer support, content moderation

## Output Files

| File | Contents |
|------|----------|
| `.tmp/ai_audit_results.json` | Complete audit: nodes, prompts, costs, security findings |
