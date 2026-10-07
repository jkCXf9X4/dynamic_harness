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
  - runtime.md
  - agent.md
  - ../../product-breakdown/05-operation/guides/custom-agents/README.md
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
    provider_ignore: list[str] = field(default_factory=list)
    provider_allow_fallbacks: bool = True
    provider_force: str | None = None
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
    model: str = "gpt-4o",                  # Model name
    base_url: str | None = None,            # None → OpenAI default
    api_key: str | None = None,             # None → uses env / AsyncOpenAI
    verify_ssl: bool = True,
    provider_ignore: list[str] | None = None,    # OpenRouter providers to exclude
    provider_allow_fallbacks: bool = True,       # Allow OpenRouter fallback routing
    provider_force: str | None = None,           # Pin a single OpenRouter provider (disables fallbacks)
)
```

Supports both OpenAI and OpenRouter endpoints. For OpenRouter, set `base_url="https://openrouter.ai/api/v1"`.

### Configuration

Configuration is split into two files:

**Shell config** (`~/.bashrc`, `~/.zshrc`, etc.) — secrets only:
```bash
export OPENROUTER_API_KEY=sk-or-v1-your-key    # Primary key
export OPENAI_API_KEY=sk-...                   # Fallback key
```

**`harness.json`** — structured settings:
```json
{
  "model": "openrouter/deepseek/deepseek-v4-flash-0731",
  "llm": {
    "verify_ssl": true
  },
  "providers": {
    "openrouter": {
      "env": ["OPENROUTER_API_KEY", "OPENAI_API_KEY"],
      "base_url": "https://openrouter.ai/api/v1",
      "provider_ignore": ["gmicloud", "SiliconFlow", "Baidu"],
      "provider_allow_fallbacks": true,
      "provider_force": "DeepInfra",
      "models": {
        "deepseek/deepseek-v4-flash-0731": {"name": "DeepSeek V4 Flash 0731"}
      }
    }
  }
}
```

The top-level `model` selects the default model in `<provider>/<model>` form;
`llm` carries only the general call behavior; `providers` carries each
provider's credential source (`env`), endpoint, OpenRouter routing, and model
catalog.

**Discovery (layered)**: `~/.config/dynamic-harness/harness.json` is the common base, overlaid by `./harness.json` (or explicit `--config`); local keys override the base per-field.

**Precedence**: CLI args (`--model`, `--provider`, `--base-url`, `--api-key`) → `harness.json` → built-in defaults.

## `ProviderRegistry` (named providers from config → built instances)

`ProviderRegistry.from_config(config)` builds a registry from a harness
config; `resolve(model_ref)` turns a `<provider>/<model>` ref into a
`ResolvedModel` (pure — constructs nothing); `select()` builds the provider for
the ref and marks it active; `api_key_for(provider_id)` walks the provider's
ordered `env` names in the environment only; `close_all()` releases every built
instance. Credentials are never read from the config file — a run with no
credential stays keyless and the agent fails with a recorded reason.

```python
from dynamic_harness.config import HarnessConfig
from dynamic_harness.llm.registry import ProviderRegistry

registry = ProviderRegistry.from_config(HarnessConfig())
llm = registry.select("openrouter/deepseek/deepseek-v4-flash-0731")
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
        messages.append(tool_message_parts(result.content, result.images))
    # Continue loop
else:
    # No tool calls — treat content as report summary
    agent.report(ReportPayload(summary=response.content))
```