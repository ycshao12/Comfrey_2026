import logging
import types
from typing import Any, Callable, Dict

from .config import ComfreyConfig

logger = logging.getLogger(__name__)


class BytecodeInstrumentor:
    """Entry-function instrumentation backed by Python bytecode generation.

    The paper places Comfrey between LLM/RAG output generation and downstream
    consumption. The generated wrapper calls the original entry function, then
    immediately invokes the Comfrey processing hook before returning to the
    downstream software component.
    """

    def __init__(self, config: ComfreyConfig):
        self.config = config
        self.instrumented_functions: Dict[str, Dict[str, Any]] = {}
        self._bytecode_cls = None
        self._validate_dependency()

    def _validate_dependency(self):
        if not self.config.enable_bytecode_analysis:
            return
        try:
            from bytecode import Bytecode, FreeVar, Instr
        except ImportError as exc:
            if self.config.strict_paper_mode or self.config.require_bytecode_module:
                raise RuntimeError("Paper mode requires the bytecode package for entry instrumentation") from exc
            logger.info("bytecode package unavailable; bytecode instrumentation metadata disabled")
            return
        self._bytecode_cls = Bytecode
        self._instr_cls = Instr
        self._freevar_cls = FreeVar

    def instrument_entry_function(self, func: Callable, process_output: Callable) -> Callable:
        metadata = self.inspect_function(func)
        try:
            instrumented = self._build_bytecode_wrapper(func, process_output)
            metadata["instrumentation_strategy"] = "bytecode_generated_wrapper"
        except Exception as exc:
            if self.config.strict_paper_mode or self.config.require_bytecode_module:
                raise RuntimeError("Paper mode requires bytecode wrapper generation to succeed") from exc
            logger.info(f"Falling back to Python wrapper instrumentation: {exc}")
            instrumented = self._build_python_wrapper(func, process_output)
            metadata["instrumentation_strategy"] = "python_wrapper"

        instrumented.__comfrey_instrumentation__ = metadata
        self.instrumented_functions[func.__name__] = metadata
        return instrumented

    def _build_bytecode_wrapper(self, func: Callable, process_output: Callable) -> Callable:
        if self._bytecode_cls is None:
            raise RuntimeError("bytecode package is unavailable")

        bytecode = self._bytecode_cls()
        bytecode.argcount = 0
        bytecode.posonlyargcount = 0
        bytecode.kwonlyargcount = 0
        bytecode.argnames = []
        bytecode.name = getattr(func, "__name__", "instrumented")
        bytecode.filename = getattr(func, "__code__", None).co_filename if getattr(func, "__code__", None) else "<comfrey>"
        bytecode.flags = 0x04 | 0x08  # CO_VARARGS | CO_VARKEYWORDS
        bytecode.varnames = ["args", "kwargs", "raw_output"]
        bytecode.freevars = ["func", "process_output"]

        Instr = self._instr_cls
        FreeVar = self._freevar_cls
        bytecode.extend([
            Instr("LOAD_DEREF", FreeVar("func")),
            Instr("LOAD_FAST", "args"),
            Instr("BUILD_MAP", 0),
            Instr("LOAD_FAST", "kwargs"),
            Instr("DICT_MERGE", 1),
            Instr("CALL_FUNCTION_EX", 1),
            Instr("STORE_FAST", "raw_output"),
            Instr("LOAD_DEREF", FreeVar("process_output")),
            Instr("LOAD_FAST", "raw_output"),
            Instr("LOAD_DEREF", FreeVar("func")),
            Instr("LOAD_ATTR", "__name__"),
            Instr("LOAD_FAST", "args"),
            Instr("LOAD_FAST", "kwargs"),
            Instr("CALL_FUNCTION", 4),
            Instr("RETURN_VALUE"),
        ])
        code = bytecode.to_code()
        wrapper = types.FunctionType(
            code,
            {},
            getattr(func, "__name__", "instrumented"),
            closure=(
                self._make_cell(func),
                self._make_cell(process_output),
            ),
        )
        wrapper.__name__ = getattr(func, "__name__", "instrumented")
        wrapper.__doc__ = getattr(func, "__doc__", None)
        wrapper.__module__ = getattr(func, "__module__", None)
        return wrapper

    def _build_python_wrapper(self, func: Callable, process_output: Callable) -> Callable:
        def instrumented(*args, **kwargs):
            raw_output = func(*args, **kwargs)
            return process_output(raw_output, func.__name__, args, kwargs)
        instrumented.__name__ = getattr(func, "__name__", "instrumented")
        instrumented.__doc__ = getattr(func, "__doc__", None)
        instrumented.__module__ = getattr(func, "__module__", None)
        return instrumented

    def _make_cell(self, value: Any):
        def inner():
            return value
        return inner.__closure__[0]

    def inspect_function(self, func: Callable) -> Dict[str, Any]:
        code = getattr(func, "__code__", None)
        metadata = {
            "function": getattr(func, "__name__", repr(func)),
            "bytecode_enabled": self._bytecode_cls is not None,
            "instruction_count": 0,
            "instructions": [],
        }
        if code is None or self._bytecode_cls is None:
            return metadata

        bytecode = self._bytecode_cls.from_code(code)
        instructions = []
        for instr in bytecode:
            name = getattr(instr, "name", None)
            if name:
                instructions.append(name)

        metadata.update({
            "instruction_count": len(instructions),
            "instructions": instructions,
            "argcount": code.co_argcount,
            "name": code.co_name,
        })
        return metadata
