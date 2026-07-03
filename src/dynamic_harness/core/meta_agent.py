from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

from ..core.agent import HARNESS_GUIDELINES, Agent
from ..core.runtime import Runtime
from ..core.task import ReportPayload, Task
from ..llm.provider import LLMProvider


def _clean_code(code: str) -> str:
    code = code.strip()
    code = re.sub(r"^```(?:python)?\s*\n?", "", code)
    code = re.sub(r"\n?\s*```\s*$", "", code)
    return code.strip()


class MetaAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        task: Task,
        runtime: Runtime,
        parent: Agent | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        super().__init__(agent_id, task, runtime, parent)
        self.llm = llm

    async def run(self) -> None:
        try:
            class_name, code = await self._generate_agent_code()
            filepath = self._save_code(class_name, code)
            cls = self._load_class(class_name, filepath)
            self._runtime.register_agent_class(class_name, cls)

            specialist = self.spawn(
                f"Execute: {self.task.description}",
                agent_type=class_name,
            )
            await specialist.run()

            self.report(ReportPayload(
                task_id=self.task.id,
                summary=f"Generated agent '{class_name}' from:\n{code}",
                next_actions=[],
            ))
        except Exception as e:
            self.fail(str(e))

    async def _generate_agent_code(self) -> tuple[str, str]:
        if self.llm:
            system = (
                f"You generate Python classes for a recursive agent harness.\n\n"
                f"{HARNESS_GUIDELINES}\n\n"
                f"Generate a complete Python class that extends `Agent`. "
                f"The class must implement `async def run(self) -> None`.\n\n"
                f"Rules:\n"
                f"- Start with `from __future__ import annotations`.\n"
                f"- The constructor signature MUST be:\n"
                f"  `def __init__(self, agent_id: str, task: Task, runtime: Runtime, parent: Agent | None = None):`\n"
                f"- Import Agent from `dynamic_harness.core.agent`.\n"
                f"- Import ReportPayload, Task from `dynamic_harness.core.task`.\n"
                f"- Import Runtime from `dynamic_harness.core.runtime`.\n"
                f"- Do NOT use `typing.Optional` — use `X | None` syntax (requires `from __future__ import annotations`).\n"
                f"- Use `self.spawn()` to create sub-agents when the task needs decomposition.\n"
                f"- Call `self.report(ReportPayload(...))` with findings.\n"
                f"- Access task metadata via `self.task.metadata` (dict).\n"
                f"- Write files via `self._runtime.artifact_store.write_text(artifact_id, filename, content)`.\n"
                f"- Do NOT reference `self.runtime` — use `self._runtime` if you need the Runtime.\n"
                f"- Return ONLY valid Python code. No markdown fences, no explanations, no docstrings beyond inline comments."
            )
            user = f"Task to design agent for: {self.task.description}"
            resp = await self.llm.generate(system, user)
            code = _clean_code(resp.content)
        else:
            code = self._fallback_code()

        class_name = self._extract_class_name(code)
        return class_name, code

    def _extract_class_name(self, code: str) -> str:
        for line in code.splitlines():
            line = line.strip()
            if line.startswith("class ") and ":" in line:
                return line.split()[1].split("(")[0].split(":")[0]
        return "GeneratedAgent"

    def _save_code(self, class_name: str, code: str) -> Path:
        root = self._runtime.generated_root
        root.mkdir(parents=True, exist_ok=True)
        init = root / "__init__.py"
        if not init.exists():
            init.write_text("")
        filepath = root / f"{class_name.lower()}.py"
        filepath.write_text(code)
        return filepath

    def _load_class(self, class_name: str, filepath: Path) -> type[Agent]:
        pkg = self._runtime.generated_root.name
        module_name = f"{pkg}.{class_name.lower()}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec from {filepath}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        cls = getattr(module, class_name)
        if not issubclass(cls, Agent):
            raise TypeError(f"{class_name} does not extend Agent")
        return cls

    def _fallback_code(self) -> str:
        return (
            'from dynamic_harness.core.agent import Agent\n'
            'from dynamic_harness.core.task import ReportPayload, Task\n'
            'from dynamic_harness.core.runtime import Runtime\n\n\n'
            'class GeneratedAgent(Agent):\n'
            '    def __init__(\n'
            '        self, agent_id: str, task: Task,\n'
            '        runtime: Runtime, parent: Agent | None = None,\n'
            '    ) -> None:\n'
            '        super().__init__(agent_id, task, runtime, parent)\n\n'
            '    async def run(self) -> None:\n'
            '        self.report(ReportPayload(\n'
            '            task_id=self.task.id,\n'
            '            summary=f"Generated agent executed: {self.task.description}",\n'
            '        ))\n'
        )