# Comfrey Framework - Runtime Prevention of LLM Integration Failures

## Project Overview

This repository contains the artifact for the ICSE 2026 paper
"Comfrey: Mitigating Integration Failures in LLM-enabled Software at Run-Time".
The primary affiliation is Shanghai Innovation Institute.

Comfrey is a runtime framework for preventing LLM integration failures. Implemented according to the methodology section (Section 4) of the paper, it serves as a middleware layer between AI components (LLM and RAG) and downstream software components, automatically detecting and adapting AI component outputs that violate format, syntax, and repetition requirements.

### Core Design Principles

1. **Three-stage error handling workflow** - Format → Syntax → Repetition
2. **Low-overhead design** - Prioritize rule-based techniques, avoid computation-intensive methods
3. **Requirement acquisition mechanism** - Extract requirements from software expectations and application scenarios
4. **Two-stage similarity detection** - TF-IDF + sentence embedding similarity

## Main Features

### 1. Three-stage Error Detection and Repair

#### Stage 1: Format Error Resolution (Section 4.3)
- **Template discrepancy detection**: Uses finite state automaton (FSA) validation with element threshold τ_element=3
- **Improper data segmentation**: Dictionary validation + syntax tree analysis
- **Incorrect context construction**: Two-stage similarity detection (TF-IDF + sentence embedding)

#### Stage 2: Syntax Error Resolution (Section 4.4)  
- **Syntax-parser misalignment**: Compiler/parser syntax validation, AST refinement
- **Inconsistent lexical features**: Unicode script detection + n-gram frequency analysis

#### Stage 3: Repetition Error Resolution (Section 4.5)
- **Redundant software behavior**: History checking, deterministic function detection
- **Redundant semantics**: Two-stage similarity detection with unified threshold τ=0.7

### 2. Requirement Acquisition Mechanism (Section 4.2)

#### Software Expectation Requirement Extraction
- Extract requirements from downstream software components through static analysis
- Identify LLM output consumption points
- Extract templates, data block specifications, context construction rules, parser syntax

#### Application Scenario Requirement Characterization
- 7 scenario-driven requirements
- Format dimension: intact textual elements, content relevance
- Syntax dimension: consistent lexical features
- Repetition dimension: absence of unnecessary software behavior repetition, succinct content, context semantic redundancy

### 3. Low-overhead Design

- **Rule priority**: Prioritize computation-efficient rule-based techniques
- **Lightweight models**: Use 0.6B parameter embedding model (all-MiniLM-L6-v2)
- **Early termination**: Iteration-aware termination mechanism
- **Two-stage detection**: TF-IDF first, then sentence embedding (only when necessary)

## Installation and Usage

### System Requirements

- Python 3.8+
- Memory: At least 2GB RAM
- Storage: At least 500MB available space

### Quick Installation

```bash
# Clone the repository
git clone <repository-url>
cd Comfrey_fixtool

# Install dependencies
pip install -r source_code/comfrey_code/requirements.txt

# Install spaCy English model
python -m spacy download en_core_web_sm

# Verify installation
python source_code/comfrey_code/basic_function_test.py
```

### Basic Usage

```python
from comfrey_code.src.comfrey_core import ComfreyFramework
from comfrey_code.src.config import ComfreyConfig

# Create lightweight configuration
config = ComfreyConfig.create_lightweight_config()
comfrey = ComfreyFramework(config)

# Extract requirements
requirements = comfrey.extract_requirements_from_codebase(
    target_directory=".",
    entry_functions=["main", "process", "handle"]
)

# Use decorator to wrap AI components
@comfrey
def my_llm_function(prompt):
    # Your LLM call code
    return llm_response

# Automatic detection and repair
result = my_llm_function("Generate some code")
```

### Advanced Usage Example

```python
from comfrey_code.src.comfrey_core import ComfreyFramework
from comfrey_code.src.config import ComfreyConfig

# Create comprehensive configuration
config = ComfreyConfig.create_comprehensive_config()
config.similarity_threshold = 0.8
config.max_repair_iterations = 5

# Initialize framework
comfrey = ComfreyFramework(config, target_directory="./my_app")

# Extract and analyze requirements
requirements = comfrey.extract_requirements_from_codebase(
    target_directory="./my_app",
    entry_functions=["main", "run", "start", "process"]
)

# Wrap multiple AI functions
@comfrey
def code_generator(prompt, language="python"):
    # Code generation logic
    return generated_code

@comfrey  
def text_analyzer(text):
    # Text analysis logic
    return analysis_result

# Use and monitor
result1 = code_generator("Create a web scraper", "python")
result2 = text_analyzer("Sample text for analysis")

# Get statistics
stats = comfrey.get_statistics()
print(f"Total invocations: {stats['total_invocations']}")
print(f"Format errors detected: {stats['format_errors_detected']}")
print(f"Successful repairs: {stats['repairs_successful']}")
```

### Run Examples

```bash
# Run basic functionality test
python source_code/comfrey_code/basic_function_test.py

# Run usage example
python source_code/comfrey_code/example_usage.py

# Run paper test
python source_code/comfrey_code/final_paper_test.py
```
