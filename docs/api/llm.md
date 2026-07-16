---
title: "LLM Provider Reference"
category: api
module: dynamic_harness.llm.provider
classes:
  - LLMProvider (ABC)
  - LLMConfig
  - LLMResponse
  - ToolCallData
  - ToolCallResponse
impl:
  - dynamic_harness.llm.openai_provider.OpenAIProvider
summary: >
  Abstract LLM interface and default OpenAI/OpenRouter implementation.
  The LLMProvider ABC defines three generation methods; OpenAIProvider
  implements them using the AsyncOpenAI client.
related:
  - api/runtime.md
  - api/agent.md
  - guides/custom-agents.md
---

# LLM Provider

```python
from dynamic_harness.llm.provider import LLMProvider, LLMConfig, LLMResponse, ToolCallData, ToolCallResponse
from dynamic_harness.llm.openai_provider import OpenAIProvider
```

## Data Types

### `LLMConfig`

```python
@dataclass
class LLMConfig:
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int | None = None
```

### `LLMResponse` (simple generation)

```python
@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict | None = None  # {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
```

### `ToolCallData`

```python
@dataclass
class ToolCallData:
    id: str                  # Tool call ID from the LLM
    name: str                # Tool name
    arguments: dict[str, Any]  # Parsed arguments
```

### `ToolCallResponse` (tool-calling generation)

```python
@dataclass
class ToolCallResponse:
    content: str | None           # Text content (may be None if tool calls present)
    tool_calls: list[ToolCallData] | None  # Tool calls (may be None if text-only)
    model: str
    usage: dict | None
```

## `LLMProvider` (Abstract Base Class)

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        system: str,
        user: str,
        config: LLMConfig | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        config: LLMConfig | None = None,
    ) -> ToolCallResponse: ...

    @abstractmethod
    async def generate_structured(
        self,
        system: str,
        user: str,
        response_model: type,
        config: LLMConfig | None = None,
    ) -> object: ...
```

### Method Details

#### `generate(system, user, config=None) -> LLMResponse`

Simple text generation without tool calling. Used for summarization and non-interactive tasks.

#### `generate_with_tools(messages, tools, config=None) -> ToolCallResponse`

The primary method used by the agent loop. Takes the full message history and available tool schemas, returns either text content or tool calls.

- `messages`: List of OpenAI-format message dicts (`{"role": "system|user|assistant|tool", "content": ...}`)
- `tools`: List of OpenAI function-calling schemas from `ToolRegistry.openai_schemas()`

#### `generate_structured(system, user, response_model, config=None) -> object`

Structured output generation using Pydantic model parsing. Returns a validated instance of `response_model`.

## `OpenAIProvider` (Default Implementation)

```python
from dynamic_harness.llm.openai_provider import OpenAIProvider
```

### Constructor

```python
OpenAIProvider(
    api_key: str,                          # OpenAI/OpenRouter API key
    model: str = "deepseek/deepseek-v4-flash",
    base_url: str | None = None,           # Default: https://api.openai.com/v1
    temperature: float = 0.0,
    max_tokens: int | None = None,
    config: LLMConfig | None = None,       # Override with config object
)
```

Supports both OpenAI and OpenRouter endpoints. For OpenRouter, set `base_url="https://openrouter.ai/api/v1"`.

### Configuration Precedence

```
Constructor args > config object > defaults
```

### Environment Variables

The CLI loads these via `python-dotenv`:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key    # Primary key
OPENAI_API_KEY=sk-...                   # Fallback key
LLM_MODEL=deepseek/deepseek-v4-flash    # Model override
LLM_BASE_URL=https://openrouter.ai/api/v1  # Base URL override
```

## Creating a Custom Provider

Implement `LLMProvider` for any LLM backend (Anthropic, local models, etc.):

```python
from dynamic_harness.llm.provider import LLMProvider, LLMResponse, ToolCallResponse

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model

    async def generate(self, system, user, config=None):
        # Implement text generation
        ...

    async def generate_with_tools(self, messages, tools, config=None):
        # Implement tool-calling generation
        ...

    async def generate_structured(self, system, user, response_model, config=None):
        # Implement structured output
        ...
```

Then inject via Runtime:

```python
provider = AnthropicProvider(api_key="...")
runtime.set_llm(provider)
```

## How the Agent Loop Uses the LLM

```python
# Inside Agent._run_loop():

# 1. Get tool schemas from registry
tools = runtime.tool_registry.openai_schemas()

# 2. Call LLM with full message history + tools
response = await llm.generate_with_tools(messages, tools)

# 3. Branch on response type
if response.tool_calls:
    # Execute each tool call, feed results back as messages
    for tc in response.tool_calls:
        result = await registry.execute(tc.name, tc.id, agent=self, **tc.arguments)
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result.content})
    # Continue loop
else:
    # No tool calls — treat content as report summary
    agent.report(ReportPayload(summary=response.content))
```