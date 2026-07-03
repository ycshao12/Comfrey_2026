# Comfrey artifact source file.

import os
import sys
import ast
import json
import logging
import collections
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

try:
    import jedi
except ImportError:
    jedi = None

try:
    import networkx as nx
except ImportError:
    nx = None

try:
    import beniget
except ImportError:
    beniget = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pyan
    PYAN_AVAILABLE = True
except ImportError:
    PYAN_AVAILABLE = False
    logging.warning("pyan3 not available, using fallback call graph analysis")

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.types import ErrorType
from src.config import ComfreyConfig

logger = logging.getLogger(__name__)

class RequirementType(Enum):
    OUTPUT_TEMPLATE = "output_template"
    DATA_CHUNK_SPEC = "data_chunk_specification"
    CONTEXT_CONSTRUCTION = "context_construction"
    PROGRAMMING_LANGUAGE = "programming_language"
    API_SIGNATURE = "api_signature"
    SCENARIO_BASED = "scenario_based"

@dataclass
class ExtractedRequirement:
    type: RequirementType
    source_location: str  
    pattern: str
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RequirementExtractionResult:
    requirements: List[ExtractedRequirement] = field(default_factory=list)
    call_graph: Any = field(default_factory=lambda: nx.DiGraph() if nx else SimpleDiGraph())
    llm_output_consumers: List[str] = field(default_factory=list)
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)

class SimpleDiGraph:
    def __init__(self):
        self._edges = {}
        self._nodes = {}

    def add_node(self, node, **attrs):
        self._nodes.setdefault(node, {}).update(attrs)
        self._edges.setdefault(node, {})

    def add_edge(self, source, target, **attrs):
        self.add_node(source)
        self.add_node(target)
        self._edges.setdefault(source, {})[target] = attrs

    def nodes(self):
        return list(self._nodes.keys())

    def successors(self, node):
        return list(self._edges.get(node, {}).keys())

    def edges(self):
        return [(source, target) for source, targets in self._edges.items() for target in targets]

    def __len__(self):
        return len(self._edges)

class RequirementExtractor:
    
    def __init__(self, config: ComfreyConfig):
        self.config = config
        self._validate_paper_dependencies()
        self.call_graph = nx.DiGraph() if nx else SimpleDiGraph()
        self.data_flow_graph = nx.DiGraph() if nx else SimpleDiGraph()
        self.llm_output_consumers = []
        self.extracted_requirements = []
        
        self.template_patterns = self._initialize_template_patterns()
        self.syntax_patterns = self._initialize_syntax_patterns()
        self.segmentation_patterns = self._initialize_segmentation_patterns()

    def _validate_paper_dependencies(self):
        if not self.config.strict_paper_mode:
            return
        missing = []
        if jedi is None:
            missing.append("jedi")
        if nx is None:
            missing.append("networkx")
        if beniget is None:
            missing.append("beniget")
        if not PYAN_AVAILABLE:
            missing.append("pyan3")
        if missing:
            raise ImportError(
                "Paper mode requires the static-analysis dependencies used in the paper: "
                + ", ".join(missing)
            )
        
    def extract_requirements_from_codebase(self, 
                                         target_directory: str,
                                         entry_functions: List[str] = None) -> RequirementExtractionResult:

        logger.info(f"Starting requirement extraction from {target_directory}")
        
        self._build_call_graph(target_directory, entry_functions)
        
        self._analyze_data_flow()
        
        self._identify_llm_output_consumers()
        
        self._extract_requirements_from_consumers()
        
        self._add_scenario_requirements()
        
        result = RequirementExtractionResult(
            requirements=self.extracted_requirements,
            call_graph=self.call_graph,
            llm_output_consumers=self.llm_output_consumers,
            analysis_metadata={
                "total_functions_analyzed": len(self.call_graph),
                "llm_consumers_found": len(self.llm_output_consumers),
                "requirements_extracted": len(self.extracted_requirements)
            }
        )
        
        logger.info(f"Extraction complete: {len(self.extracted_requirements)} requirements found")
        return result
    
    def _build_call_graph(self, target_directory: str, entry_functions: List[str] = None):
        logger.debug("Building call graph with professional tools")
        
        if PYAN_AVAILABLE:
            success = self._build_call_graph_with_pyan3(target_directory)
            if success:
                logger.info("Successfully built call graph with Pyan3")
                return
            if self.config.strict_paper_mode:
                raise RuntimeError("Paper mode requires successful Pyan3 call graph construction")
        
        logger.info("Using enhanced AST analysis for call graph")
        self._build_call_graph_with_ast(target_directory)
    
    def _build_call_graph_with_pyan3(self, target_directory: str) -> bool:
        try:
            root_directory = os.path.abspath(target_directory)
            python_files = []
            for root, dirs, files in os.walk(target_directory):
                for file in files:
                    if file.endswith('.py'):
                        python_files.append(os.path.abspath(os.path.join(root, file)))
            
            if not python_files:
                return False
            
            pyan_logger = logging.getLogger(f"{__name__}.pyan3")
            pyan_logger.setLevel(logging.WARNING)
            analyzer = pyan.CallGraphVisitor(
                python_files,
                root=root_directory,
                logger=pyan_logger
            )

            for source, targets in getattr(analyzer, 'uses_edges', {}).items():
                for target in targets:
                    self.call_graph.add_edge(str(source), str(target), type='uses')

            for source, targets in getattr(analyzer, 'defines_edges', {}).items():
                for target in targets:
                    self.call_graph.add_edge(str(source), str(target), type='defines')
            
            self._extract_llm_info_from_pyan3(analyzer)
            
            logger.info(f"Pyan3 analysis complete: {len(self.call_graph.nodes())} nodes, {len(self.call_graph.edges())} edges")
            return True
            
        except Exception as e:
            logger.error(f"Pyan3 analysis failed: {e}")
            return False
    
    def _build_call_graph_with_ast(self, target_directory: str):
        import os
        python_files = []
        for root, dirs, files in os.walk(target_directory):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content, filename=file_path)
                visitor = CallGraphVisitor(file_path, self)
                visitor.visit(tree)
                
                for func_name, calls in visitor.call_graph.items():
                    for call in calls:
                        self.call_graph.add_edge(func_name, call)
                
                self._analyze_def_use_chains_for_file(file_path, tree)
                
            except Exception as e:
                logger.warning(f"Failed to parse {file_path}: {e}")
                continue
    
    def _extract_llm_info_from_pyan3(self, analyzer):
    
        llm_patterns = ['openai', 'gpt', 'claude', 'llm', 'generate']
        
        for node_groups in getattr(analyzer, 'nodes', {}).values():
            nodes = node_groups if isinstance(node_groups, list) else [node_groups]
            for node in nodes:
                node_name = str(getattr(node, 'name', node))
                if any(pattern in node_name.lower() for pattern in llm_patterns):
                    self.llm_output_consumers.append({
                        'function': node_name,
                        'location': node_name,
                        'operation': node_name,
                        'context': {
                            'type': 'llm_output_processing',
                            'source': 'pyan3',
                            'code': node_name
                        }
                    })
    
    def _analyze_def_use_chains_for_file(self, file_path: str, tree: ast.AST):
       
        try:
            if beniget is None:
                return
            duc = beniget.DefUseChains()
            duc.visit(tree)
            
            for var_name in self.llm_output_consumers:
                if var_name in duc.chains:
                    chain = duc.chains[var_name]
                    usage_patterns = self._analyze_variable_usage_patterns(chain)
                    logger.debug(f"Variable {var_name} usage patterns: {usage_patterns}")
                    
        except Exception as e:
            logger.debug(f"Beniget analysis failed {file_path}: {e}")
    
    def _analyze_variable_usage_patterns(self, chain) -> Dict[str, Any]:
        return {
            'usage_count': len(chain.users) if hasattr(chain, 'users') else 0,
            'definition_count': len(chain.assigners) if hasattr(chain, 'assigners') else 0,
            'chain_length': len(chain.nodes) if hasattr(chain, 'nodes') else 0
        }
    
    def _analyze_data_flow(self):
    
        logger.debug("Analyzing data flow")
        
        llm_output_vars = set()
        
        for func_name in self.call_graph.nodes():
            callees = list(self.call_graph.successors(func_name))
            for callee in callees:
                if self._is_llm_api_call(callee):
                    if '::' in func_name:
                        var_name = func_name.split('::')[1]
                        llm_output_vars.add(var_name)
                        logger.debug(f"Added LLM output variable: {var_name}")
                    else:
                        var_name = self._infer_output_variable(func_name, callee)
                        if var_name:
                            llm_output_vars.add(var_name)
                            logger.debug(f"Inferred LLM output variable: {var_name}")
        
        self._build_data_flow_graph(llm_output_vars)
        
        logger.debug(f"Found {len(llm_output_vars)} LLM output variables")
    
    def _identify_llm_output_consumers(self):
     
        logger.debug("Identifying LLM output consumers")
        
        for func_name in self.call_graph.nodes():
            if '::' in func_name:
                continue
                
            callees = list(self.call_graph.successors(func_name))
            for callee in callees:
                if self._is_llm_output_processing(callee):
                    consumer_info = {
                        'function': func_name,
                        'location': f"{func_name}",
                        'operation': callee,
                        'context': {'type': 'llm_output_processing'}
                    }
                    self.llm_output_consumers.append(consumer_info)
                    logger.debug(f"Found LLM output consumer: {func_name} -> {callee}")
    
    def _is_llm_output_processing(self, operation: str) -> bool:
        processing_patterns = [
            'json.loads', 'json.dumps', '.json()', 'json.load', 'json.dump',
            'xml.etree', 'BeautifulSoup', 'xmltodict', 'yaml.load', 'yaml.dump',
            
            '.split(', '.strip(', '.replace(', '.format(', '.join(', '.lower(', '.upper(',
            '.startswith(', '.endswith(', '.find(', '.index(', 'regex', 're.search', 're.match',
            
            'ast.parse', 'compile(', 'exec(', 'eval(', 'subprocess', 'os.system',
            
            'open(', '.write(', '.read(', '.save(', '.load(',
            
            'pandas', '.DataFrame', '.to_csv', '.to_json', '.to_dict',
            
            'jinja2', '.render(', 'Template', '.substitute(',
            
            'validate', 'check', 'verify', 'assert', 'isinstance', 'hasattr',
            
            'print(', 'log', 'display', 'show', 'render'
        ]
        
        operation_lower = operation.lower()
        return any(pattern in operation_lower for pattern in processing_patterns)
    
    def _extract_requirements_from_consumers(self):
    
        logger.debug("Extracting requirements from consumer code")
        
        for consumer in self.llm_output_consumers:
            if not isinstance(consumer, dict):
                consumer = {
                    'function': str(consumer),
                    'location': str(consumer),
                    'operation': str(consumer),
                    'context': {
                        'type': 'llm_output_processing',
                        'source': 'legacy',
                        'code': str(consumer)
                    }
                }
            operation = consumer.get('operation', '')
            
            self._extract_template_requirements(consumer)
            self._extract_segmentation_requirements(consumer)
            self._extract_context_requirements(consumer)
            self._extract_syntax_requirements(consumer)
            self._extract_validation_requirements(consumer)
            self._extract_format_requirements(consumer)
    
    def _extract_template_requirements(self, consumer: Dict[str, Any]):

        operation = consumer.get('operation', '')
        location = consumer.get('location', '')
        
        if 'json.loads' in operation or '.json()' in operation:
            requirement = ExtractedRequirement(
                type=RequirementType.OUTPUT_TEMPLATE,
                source_location=location,
                pattern='json_schema',
                confidence=0.9,
                details={
                    'template_type': 'structured_data',
                    'format': 'json',
                    'schema_hints': self._extract_json_schema_hints(consumer)
                }
            )
            self.extracted_requirements.append(requirement)
        
        elif 'xml.etree' in operation or 'BeautifulSoup' in operation:
            requirement = ExtractedRequirement(
                type=RequirementType.OUTPUT_TEMPLATE,
                source_location=location,
                pattern='xml_schema',
                confidence=0.9,
                details={
                    'template_type': 'structured_data',
                    'format': 'xml',
                    'schema_hints': self._extract_xml_schema_hints(consumer)
                }
            )
            self.extracted_requirements.append(requirement)
        
        elif self._has_positional_template_pattern(operation):
            requirement = ExtractedRequirement(
                type=RequirementType.OUTPUT_TEMPLATE,
                source_location=location,
                pattern='positional_template',
                confidence=0.7,
                details={
                    'template_type': 'positional',
                    'identifiers': self._extract_positional_identifiers(consumer)
                }
            )
            self.extracted_requirements.append(requirement)
    
    def _extract_segmentation_requirements(self, consumer: Dict[str, Any]):
     
        operation = consumer.get('operation', '')
        location = consumer.get('location', '')
        
        if any(pattern in operation for pattern in ['.split(', '.splitlines(', 'textwrap.', 'chunk']):
            requirement = ExtractedRequirement(
                type=RequirementType.DATA_CHUNK_SPEC,
                source_location=location,
                pattern='text_segmentation',
                confidence=0.8,
                details={
                    'boundary_markers': self._extract_boundary_markers(consumer),
                    'chunk_size_constraints': self._extract_chunk_constraints(consumer),
                    'completeness_criteria': self._extract_completeness_criteria(consumer)
                }
            )
            self.extracted_requirements.append(requirement)
    
    def _extract_context_requirements(self, consumer: Dict[str, Any]):
  
        operation = consumer.get('operation', '')
        location = consumer.get('location', '')
        
        if any(pattern in operation for pattern in ['context', 'retrieve', 'embed', 'similarity']):
            requirement = ExtractedRequirement(
                type=RequirementType.CONTEXT_CONSTRUCTION,
                source_location=location,
                pattern='semantic_coherence',
                confidence=0.7,
                details={
                    'coherence_threshold': self._extract_coherence_threshold(consumer),
                    'similarity_metric': self._extract_similarity_metric(consumer),
                    'context_window': self._extract_context_window(consumer)
                }
            )
            self.extracted_requirements.append(requirement)
    
    def _extract_syntax_requirements(self, consumer: Dict[str, Any]):
 
        operation = consumer.get('operation', '')
        location = consumer.get('location', '')
        
        if any(pattern in operation for pattern in ['compile(', 'ast.parse', 'exec(', 'eval(']):
            requirement = ExtractedRequirement(
                type=RequirementType.PROGRAMMING_LANGUAGE,
                source_location=location,
                pattern='python_syntax',
                confidence=0.9,
                details={
                    'language': 'python',
                    'syntax_level': self._extract_syntax_level(consumer),
                    'api_signatures': self._extract_api_signatures(consumer)
                }
            )
            self.extracted_requirements.append(requirement)
    
    def _extract_validation_requirements(self, consumer: Dict[str, Any]):
   
        operation = consumer.get('operation', '')
        location = consumer.get('location', '')
        
        if any(pattern in operation.lower() for pattern in ['validate', 'check', 'verify', 'assert', 'isinstance']):
            requirement = ExtractedRequirement(
                type=RequirementType.OUTPUT_TEMPLATE,
                source_location=location,
                pattern='validation_constraint',
                confidence=0.8,
                details={
                    'validation_type': 'data_validation',
                    'constraint_pattern': operation,
                    'requirement_source': 'validation_code'
                }
            )
            self.extracted_requirements.append(requirement)
            logger.debug(f"Extracted validation requirement from {location}")
    
    def _extract_format_requirements(self, consumer: Dict[str, Any]):
    
        operation = consumer.get('operation', '')
        location = consumer.get('location', '')
        
        if any(pattern in operation.lower() for pattern in ['json', 'xml', 'yaml', 'csv']):
            format_type = 'json' if 'json' in operation.lower() else \
                         'xml' if 'xml' in operation.lower() else \
                         'yaml' if 'yaml' in operation.lower() else \
                         'csv' if 'csv' in operation.lower() else 'structured'
            
            requirement = ExtractedRequirement(
                type=RequirementType.OUTPUT_TEMPLATE,
                source_location=location,
                pattern=f'{format_type}_format',
                confidence=0.9,
                details={
                    'format_type': format_type,
                    'processing_operation': operation,
                    'requirement_source': 'format_processing'
                }
            )
            self.extracted_requirements.append(requirement)
            logger.debug(f"Extracted format requirement: {format_type} from {location}")
        
        elif any(pattern in operation.lower() for pattern in ['.split(', '.strip(', '.replace(', '.format(']):
            requirement = ExtractedRequirement(
                type=RequirementType.DATA_CHUNK_SPEC,
                source_location=location,
                pattern='string_processing',
                confidence=0.7,
                details={
                    'processing_type': 'string_manipulation',
                    'operation': operation,
                    'requirement_source': 'string_processing'
                }
            )
            self.extracted_requirements.append(requirement)
            logger.debug(f"Extracted string processing requirement from {location}")
        
        elif any(pattern in operation.lower() for pattern in ['exec(', 'eval(', 'compile(', 'ast.parse']):
            requirement = ExtractedRequirement(
                type=RequirementType.PROGRAMMING_LANGUAGE,
                source_location=location,
                pattern='code_execution',
                confidence=0.9,
                details={
                    'execution_type': 'code_compilation',
                    'operation': operation,
                    'requirement_source': 'code_execution'
                }
            )
            self.extracted_requirements.append(requirement)
            logger.debug(f"Extracted code execution requirement from {location}")
    
    def _add_scenario_requirements(self):

        logger.debug("Scenario requirements are handled separately by ScenarioRequirementManager")
        pass
    
    def _initialize_template_patterns(self) -> List[str]:
        return [
            r'json\.loads\(',
            r'\.json\(\)',
            r'xml\.etree',
            r'BeautifulSoup',
            r'yaml\.load',
            r'csv\.reader',
            r'\.format\(',
            r'%\s*\(',
            r'f["\'].*{.*}.*["\']'
        ]
    
    def _initialize_syntax_patterns(self) -> List[str]:

        return [
            r'compile\(',
            r'ast\.parse',
            r'exec\(',
            r'eval\(',
            r'import\s+ast',
            r'tokenize\.',
            r'\.py$',
            r'subprocess\.run'
        ]
    
    def _initialize_segmentation_patterns(self) -> List[str]:

        return [
            r'\.split\(',
            r'\.splitlines\(',
            r'textwrap\.',
            r'chunk',
            r'segment',
            r'\.join\(',
            r'len\(',
            r'[:]\s*\d+'
        ]
    
    def _is_llm_api_call(self, function_call: str) -> bool:

        llm_indicators = [
            'openai', 'gpt', 'chatgpt', 'ChatCompletion', 'Completion',
            'ChatOpenAI', 'AzureChatOpenAI', 'openai_call', 'llm_call',
            
            'claude', 'anthropic', 'ChatAnthropic', 'Anthropic',
            'anthropic_client', 'anthropic.messages',
            
            'gemini', 'genai', 'GenerativeModel', 'google.generativeai',
            
            'llm', 'language_model', 'chat_model', 'generate', 'complete',
            'BaseChatModel', 'LLMClient', 'LLMEndpoint', 'create_llm',
            
            'huggingface', 'together', 'cohere', 'replicate', 'palm',
            'llama', 'mistral', 'qianfan', 'tongyi', 'baichuan',
            
            'chat', 'completion', 'embedding', 'model', 'api', 'client',
            'messages.create', 'chat.completions', 'completions.create',
            
            'api_request', 'webhook_request', 'send_message', 'ask_question',
            'get_response', 'generate_text', 'chat_completion'
        ]
        
        function_call_lower = function_call.lower()
        return any(indicator in function_call_lower for indicator in llm_indicators)
    
    def _is_core_functionality_branch(self, flow: Dict[str, Any]) -> bool:

        context = flow.get('context', {})
        
        if any(keyword in str(context).lower() for keyword in ['except', 'error', 'fail', 'catch']):
            return False
        
        if any(keyword in str(context).lower() for keyword in ['log', 'debug', 'print', 'warn']):
            return False
            
        return True
    
    def _extract_return_variable(self, func_name: str, callee: str) -> Optional[str]:
    
        if '=' in callee:
            parts = callee.split('=')
            if len(parts) >= 2:
                return parts[0].strip()
        return None
    
    def _build_data_flow_graph(self, llm_output_vars: Set[str]):
      
        for var in llm_output_vars:
            self.data_flow_graph.add_node(var, type='llm_output')
            self.data_flow_graph.add_edge(var, f"{var}_usage", operation='usage')
    
    def _extract_json_schema_hints(self, consumer: Dict[str, Any]) -> Dict[str, Any]:
        text = self._consumer_text(consumer)
        properties = {}
        for key in re.findall(r"\[['\"]([A-Za-z_][\w-]*)['\"]\]", text):
            properties[key] = {"required": True}
        for key in re.findall(r"\.get\(['\"]([A-Za-z_][\w-]*)['\"]", text):
            properties.setdefault(key, {"required": False})
        return {
            'type': 'object' if properties else 'unknown',
            'properties': properties,
            'source': 'static_consumer_code'
        }
    
    def _extract_xml_schema_hints(self, consumer: Dict[str, Any]) -> Dict[str, Any]:
        text = self._consumer_text(consumer)
        root_match = re.search(r"find(?:all)?\(['\"]/?([A-Za-z_][\w.-]*)", text)
        return {
            'root_element': root_match.group(1) if root_match else 'unknown',
            'namespace': None,
            'source': 'static_consumer_code'
        }
    
    def _has_positional_template_pattern(self, operation: str) -> bool:
     
        return any(pattern in operation for pattern in ['.format(', '%', 'f"', "f'"])
    
    def _extract_positional_identifiers(self, consumer: Dict[str, Any]) -> List[str]:
        text = self._consumer_text(consumer)
        identifiers = re.findall(r'\{([A-Za-z_][\w-]*)\}', text)
        identifiers.extend(re.findall(r'%\(([A-Za-z_][\w-]*)\)', text))
        return list(dict.fromkeys(identifiers))
    
    def _extract_boundary_markers(self, consumer: Dict[str, Any]) -> List[str]:
        text = self._consumer_text(consumer)
        markers = []
        for match in re.findall(r"\.split\((['\"])(.*?)\1\)", text):
            markers.append(match[1])
        if ".splitlines(" in text:
            markers.append("\n")
        return markers or ['.', '!', '?', '\n', '\n\n']
    
    def _extract_chunk_constraints(self, consumer: Dict[str, Any]) -> Dict[str, Any]:
        text = self._consumer_text(consumer)
        numbers = [int(value) for value in re.findall(r'\b(?:chunk_size|max_tokens|max_size|limit)\s*=\s*(\d+)', text)]
        slice_limits = [int(value) for value in re.findall(r'\[:\s*(\d+)\s*\]', text)]
        candidates = numbers + slice_limits
        if candidates:
            return {'max_size': min(candidates), 'source': 'static_consumer_code'}
        return {'max_size': None, 'min_size': None, 'source': 'not_inferred'}
    
    def _extract_completeness_criteria(self, consumer: Dict[str, Any]) -> Dict[str, Any]:
  
        return {'word_completeness': True, 'sentence_integrity': True}
    
    def _extract_coherence_threshold(self, consumer: Dict[str, Any]) -> float:
      
        return 0.7  
    
    def _extract_similarity_metric(self, consumer: Dict[str, Any]) -> str:

        return 'cosine' 
    
    def _extract_context_window(self, consumer: Dict[str, Any]) -> int:
        text = self._consumer_text(consumer)
        match = re.search(r'\b(?:top_k|k|context_window)\s*=\s*(\d+)', text)
        return int(match.group(1)) if match else 5  
    
    def _extract_syntax_level(self, consumer: Dict[str, Any]) -> str:

        return 'statement'  
    
    def _extract_api_signatures(self, consumer: Dict[str, Any]) -> List[str]:
        text = self._consumer_text(consumer)
        calls = re.findall(r'([A-Za-z_][\w.]+)\s*\(', text)
        return list(dict.fromkeys(calls))

    def _consumer_text(self, consumer: Dict[str, Any]) -> str:
        context = consumer.get('context') or {}
        parts = [
            str(consumer.get('operation', '')),
            str(consumer.get('location', '')),
            str(context.get('code', '')),
            str(context.get('source', '')),
        ]
        return "\n".join(part for part in parts if part)

    def _infer_output_variable(self, func_name: str, llm_call: str) -> Optional[str]:

        common_var_names = [
            'response', 'result', 'output', 'answer', 'content', 'text',
            'completion', 'generation', 'reply', 'message', 'data'
        ]
        
        if 'completion' in llm_call.lower():
            return 'completion'
        elif 'chat' in llm_call.lower():
            return 'response'
        elif 'generate' in llm_call.lower():
            return 'generation'
        else:
            return 'response'  


class CallGraphVisitor(ast.NodeVisitor):
 
    def __init__(self, file_path: str, extractor: 'RequirementExtractor'):
        self.file_path = file_path
        self.call_graph = collections.defaultdict(list)
        self.current_function = None
        self.extractor = extractor
    
    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_Call(self, node):
        if self.current_function:
            call_name = self._get_call_name(node)
            if call_name:
                self.call_graph[self.current_function].append(call_name)
                
                if self.extractor._is_llm_api_call(call_name):
                    logger.debug(f"Found LLM API call: {call_name} in {self.current_function}")
        
        self.generic_visit(node)
    
    def visit_Assign(self, node):

        if self.current_function and isinstance(node.value, ast.Call):
            call_name = self._get_call_name(node.value)
            if call_name and self.extractor._is_llm_api_call(call_name):
                for target in node.targets:
                    var_names = self._extract_variable_names(target)
                    for var_name in var_names:
                        logger.debug(f"Found LLM output variable: {var_name} = {call_name}")
                        self.call_graph[f"{self.current_function}::{var_name}"] = [call_name]
        
        self.generic_visit(node)
    
    def _get_call_name(self, node) -> Optional[str]:
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return f"{self._get_attr_name(node.func.value)}.{node.func.attr}"
        return None
    
    def _get_attr_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_attr_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_call_name(node) or "unknown"
        return "unknown"
    
    def _extract_variable_names(self, node) -> Set[str]:
        var_names = set()
        
        if isinstance(node, ast.Name):
            var_names.add(node.id)
        elif isinstance(node, ast.Tuple) or isinstance(node, ast.List):
            for elt in node.elts:
                var_names.update(self._extract_variable_names(elt))
        elif isinstance(node, ast.Starred):
            var_names.update(self._extract_variable_names(node.value))
        
        return var_names 
