# Comfrey

Comfrey is a runtime framework for mitigating integration failures in
LLM-enabled software. It sits between AI components, such as LLM calls or RAG
pipelines, and downstream software components, then detects and repairs outputs
that violate expected format, syntax, or repetition requirements.

This repository contains the artifact for the ICSE 2026 paper
**"Comfrey: Mitigating Integration Failures in LLM-enabled Software at
Run-Time"**.

## Highlights

- **Three-stage runtime pipeline**: format detection, syntax detection, and
  repetition detection.
- **Requirement acquisition**: static analysis extracts downstream software
  expectations and maps them to application-level scenarios.
- **Low-overhead design**: rule-based checks are prioritized, with embedding
  similarity used only where the paper method requires semantic comparison.
- **Strict paper mode**: missing paper dependencies raise errors instead of
  silently falling back to simplified behavior.
- **Integration adapters**: Python functions and LangChain-style runnables can
  be instrumented with the same runtime checks.

## Repository Layout

```text
src/
  comfrey_core.py              # Main framework entry point
  config.py                    # Runtime and paper-mode configuration
  format_detector.py           # Format failure detection
  format_repairer.py           # Format repair logic
  syntax_detector.py           # Parser and lexical failure detection
  syntax_repairer.py           # Syntax and language repair logic
  repetition_detector.py       # Software and semantic repetition detection
  repetition_repairer.py       # Repetition repair logic
  bytecode_instrumentor.py     # Runtime instrumentation support
  embedding_provider.py        # Embedding backend abstraction
  openai_compatible_client.py  # OpenAI-compatible API client
  langchain_adapter.py         # Runnable adapter

requirement_extraction/
  requirement_extractor.py     # Static requirement extraction
  scenario_requirements.py     # Scenario-level requirement characterization
  data_flow_analyzer.py
  pattern_analyzer.py

smoke_test.py                  # Lightweight verification script
requirements.txt
```

## Installation

Comfrey targets Python 3.8+.

```bash
git clone https://github.com/ycshao12/Comfrey_2026.git
cd Comfrey_2026

pip install -r requirements.txt
python -m spacy download en_core_web_sm
python smoke_test.py
```

The spaCy model is required by paper-aligned checks that use syntactic-tree
segmentation. In strict paper mode, missing runtime or static-analysis
dependencies fail fast.

## Quick Start

```python
from src.comfrey_core import ComfreyFramework
from src.config import ComfreyConfig

config = ComfreyConfig.create_lightweight_config()
comfrey = ComfreyFramework(config)

@comfrey
def generate_answer(prompt: str) -> str:
    return llm_call(prompt)

result = generate_answer("Generate a short task list")
```

Comfrey can also extract requirements from a target codebase:

```python
requirements = comfrey.extract_requirements_from_codebase(
    target_directory=".",
    entry_functions=["main", "process", "handle"],
)
```

## Paper-Aligned Mode

Use `create_paper_config()` to run the implementation path closest to the
paper method.

```python
from src.comfrey_core import ComfreyFramework
from src.config import ComfreyConfig

config = ComfreyConfig.create_paper_config()
config.embedding_model_name = "text-embedding-ada-002"
config.chat_model_name = "gpt-4.1-mini"

comfrey = ComfreyFramework(config)
```

Paper-aligned mode expects an OpenAI-compatible embedding endpoint and, for
language repair paths, an OpenAI-compatible chat completion endpoint. Configure
them with environment variables:

```bash
export OPENAI_COMPAT_BASE_URL="https://your-api-base-url"
export OPENAI_COMPAT_API_KEY="<your-api-key>"
```

Alternatively, Comfrey can read local untracked files:

```text
api_url.txt  # API base URL
key.txt      # bearer token
```

These files are ignored by `.gitignore` and should not be committed.

## Runtime Workflow

Comfrey follows the paper's three-stage workflow:

1. **Format error resolution**
   Detects template discrepancies, improper data segmentation, and incorrect
   context construction.
2. **Syntax error resolution**
   Detects parser misalignment and inconsistent lexical features, then applies
   AST- or API-assisted repair when configured.
3. **Repetition error resolution**
   Detects redundant software behavior and redundant semantics using history
   checks plus TF-IDF and embedding similarity.

## Requirement Acquisition

The requirement extractor combines static analysis and scenario
characterization:

- call graph construction with `pyan3` and `networkx`
- parser/API usage discovery with `jedi`, `beniget`, and AST traversal
- scenario-level requirements for format, syntax, and repetition dimensions

In strict paper mode, these dependencies are required. If a dependency is
missing, Comfrey raises an error rather than using a silent fallback.

## LangChain-Style Components

Runnable-style components can be wrapped through the adapter:

```python
wrapped_chain = comfrey.instrument_langchain(chain, name="retrieval_chain")
result = wrapped_chain.invoke({"query": "..."})
```

## Verification

```bash
python smoke_test.py
python -m compileall src requirement_extraction smoke_test.py
```

`smoke_test.py` checks the core instrumentation path, parser checks,
repetition repair, LangChain-style wrapping, paper-mode configuration, and
OpenAI-compatible URL/key handling without requiring real credentials.

