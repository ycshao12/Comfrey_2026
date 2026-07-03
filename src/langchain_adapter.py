# Comfrey artifact source file.
import functools
from typing import Any

from .config import ComfreyConfig


class LangChainAdapter:
    def __init__(self, framework: Any, config: ComfreyConfig):
        self.framework = framework
        self.config = config

    def instrument(self, component: Any, name: str = None) -> Any:
        if not self.config.enable_langchain_adapter:
            return component

        component_name = name or component.__class__.__name__
        if hasattr(component, "invoke"):
            return self._wrap_runnable(component, component_name)
        if callable(component):
            return self._wrap_callable(component, component_name)
        raise TypeError("LangChain adapter expects a Runnable-like or callable component")

    def _wrap_runnable(self, runnable: Any, component_name: str) -> Any:
        adapter = self

        class ComfreyRunnableWrapper:
            def __init__(self, wrapped):
                self._wrapped = wrapped

            def invoke(self, input=None, config=None, **kwargs):
                raw = self._wrapped.invoke(input, config=config, **kwargs)
                return adapter._process(raw, component_name, (input,), kwargs)

            async def ainvoke(self, input=None, config=None, **kwargs):
                raw = await self._wrapped.ainvoke(input, config=config, **kwargs)
                return adapter._process(raw, component_name, (input,), kwargs)

            def batch(self, inputs, config=None, **kwargs):
                raw_outputs = self._wrapped.batch(inputs, config=config, **kwargs)
                return [
                    adapter._process(raw, component_name, (item,), kwargs)
                    for item, raw in zip(inputs, raw_outputs)
                ]

            def __getattr__(self, item):
                return getattr(self._wrapped, item)

        return ComfreyRunnableWrapper(runnable)

    def _wrap_callable(self, component: Any, component_name: str) -> Any:
        @functools.wraps(component)
        def wrapped(*args, **kwargs):
            raw = component(*args, **kwargs)
            return self._process(raw, component_name, args, kwargs)

        return wrapped

    def _process(self, raw_output: Any, component_name: str, args: tuple, kwargs: dict) -> Any:
        self.framework.stats['total_invocations'] += 1
        processed = self.framework._process_ai_output(raw_output, component_name, args, kwargs)
        self.framework._update_execution_history(component_name, args, kwargs, raw_output, processed)
        return processed
