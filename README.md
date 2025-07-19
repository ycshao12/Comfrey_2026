# Comfrey: Run-time Prevention of LLM Integration Failures

A runtime framework for detecting and repairing LLM output errors based on the Comfrey paper methodology.

## Overview

Comfrey serves as the middle layer between AI components (LLM and RAG) and their downstream software components, automatically detecting and adapting the AI component outputs that violate the format, syntax, and repetition requirements.

## Architecture

The framework implements the three-stage workflow described in the paper:

### Stage 1: Format Error Resolution
- **Template discrepancy**: FSA validation with element threshold, element re-ordering, structure refinement, delimiter supplementation
- **Improper data segmentation**: Dictionary validation, syntactic tree analysis, fragment bridging, sliding-window re-segmentation  
- **Incorrect context construction**: Two-stage similarity detection, query-based relevance ranking, low-relevance entry removal

### Stage 2: Syntax Error Resolution
- **Syntax-parser misalignment**: Compiler/parser syntax validation, AST refinement with minimal edit distance
- **Inconsistent lexical features**: Language & structure examination, translation, grammar correction, structure standardization

### Stage 3: Repetition Error Resolution
- **Redundant software behavior**: History examination, invocation bypass
- **Redundant semantics**: Two-stage similarity detection, content de-duplication, loop termination and rollback

## Key Features

### Low-Overhead Design
- Always attempts rule-based techniques first (computationally efficient)
- Avoids computation-intensive techniques unless necessary
- Uses 0.6B-parameter embedding model only when needed
- Incorporates iteration-aware termination mechanism

### Two-Stage Similarity Detection
- **Stage 1**: TF-IDF similarity computation between every pair of data entries
- **Stage 2**: Sentence embedding similarity for pairs with scores below bottom quartile
- **Unified threshold**: τ=0.7 for all similarity detection (context construction and semantic redundancy)

### Stage-wise Error Tackling
- Resolves format errors first, then syntax errors, then repetition errors
- Minimizes interference between error types
- Tackles failures caused by combined errors
- Prioritizes errors with more severe consequences

### Requirements Extraction
- **From software expectations**: Static analysis on downstream processing code
- **From application scenarios**: 7 scenario requirements from user expectations
- Focuses on branch edges leading to function's core functionality

## Configuration

The framework supports various configuration options:

```python
from src.config import ComfreyConfig

# Lightweight configuration for minimal overhead
config = ComfreyConfig.create_lightweight_config()

# Comprehensive configuration for maximum detection capability  
config = ComfreyConfig.create_comprehensive_config()

# Custom configuration
config = ComfreyConfig(
    similarity_threshold=0.7,  # τ from paper - unified threshold for all similarity detection
    history_queue_size=10,     # N from paper - configurable and set to 10 by default
    max_repair_iterations=3,   # As specified in paper - retries up to 3 times
    element_threshold=3,       # τ_element from paper - threshold for missing/extraneous elements (3 by default)
    embedding_model_size="0.6B",  # As mentioned in paper for low overhead
    internal_redundancy_threshold=0.7,  # τ_internal - using unified threshold τ=0.7
    contextual_redundancy_threshold=0.4,  # τ_contextual from paper comments
    content_overlap_threshold=0.7,  # 70% from paper comments
    coherence_alpha=0.7,  # α from paper comments (default: 0.7)
    coherence_beta=0.6,   # β from paper comments (default: 0.6)
    coherence_gamma=0.4   # γ from paper comments (default: 0.4)
)
```

## Usage

```python
from src.comfrey_core import ComfreyFramework

# Initialize framework
comfrey = ComfreyFramework(config)

# Extract requirements from codebase
comfrey.extract_requirements_from_codebase(target_directory="./my_app")

# Use as decorator for AI component functions
@comfrey
def my_llm_function(prompt):
    # Your LLM function here
    return llm_response

# Or process outputs directly
processed_output = comfrey._process_ai_output(llm_output, "function_name", args, kwargs)
```

## Implementation Details

### Format Detection
- **Template discrepancy**: Uses finite state automata (FSA) validation with element threshold τ_element=3
- **Data segmentation**: Implements InRAG-2 enhanced algorithms for word completeness and sentence integrity
- **Context construction**: Two-stage similarity detection with bottom quartile threshold

### Syntax Detection  
- **Parser misalignment**: Proactively reuses compiler/parser syntax checking modules
- **Lexical features**: Unicode script detection, n-gram frequency analysis, dictionary validation
- **Low overhead**: Focuses on branch edges for function's core functionality

### Repetition Detection
- **Software behavior**: Maintains history queue (N=10) for tool/function invocations
- **Semantic redundancy**: Uses same two-stage similarity detection as context construction
- **Unified threshold**: τ=0.7 for all semantic redundancy detection

### Repair Strategies
- **Format**: Element re-ordering, fragment bridging, RAG re-ranking approaches
- **Syntax**: AST refinement with minimal edit distance, grammar checker integration
- **Repetition**: Invocation bypass, content de-duplication, loop termination

## Paper Alignment

This implementation follows the exact methodology described in the Comfrey paper:

- **Section 4.2**: Obtaining the Requirements
- **Section 4.3**: Resolving Format Errors  
- **Section 4.4**: Resolving Syntax Errors
- **Section 4.5**: Resolving Repetition Errors

All thresholds, algorithms, and design decisions are based on the paper specifications.

### Parameter Mapping to Paper

All default parameters are set exactly as specified in the paper:

| Parameter | Paper Reference | Default Value | Description |
|-----------|----------------|---------------|-------------|
| `similarity_threshold` | τ=0.7 | 0.7 | Unified similarity threshold for context construction and semantic redundancy |
| `element_threshold` | τ_element | 3 | Threshold for missing/extraneous elements in template discrepancy |
| `history_queue_size` | N | 10 | History queue size for redundant software behavior detection |
| `max_repair_iterations` | "retries up to 3 times" | 3 | Maximum repair iterations for syntax errors |
| `embedding_model_size` | "0.6B-parameter embedding model" | "0.6B" | Embedding model size for low overhead design |
| `internal_redundancy_threshold` | τ_internal | 0.7 | Internal redundancy detection threshold |
| `contextual_redundancy_threshold` | τ_contextual | 0.4 | Contextual redundancy detection threshold |
| `content_overlap_threshold` | "70%" | 0.7 | Content overlap threshold for redundancy detection |
| `coherence_alpha` | α (default: 0.7) | 0.7 | Weight for topical consistency |
| `coherence_beta` | β (default: 0.6) | 0.6 | Weight for query similarity |
| `coherence_gamma` | γ (default: 0.4) | 0.4 | Weight for density |

All parameters remain configurable while maintaining paper-compliant defaults. 