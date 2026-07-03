# Comfrey artifact source file.

import ast
import logging
import collections
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    import networkx as nx
except ImportError:
    nx = None

try:
    import beniget
except ImportError:
    beniget = None

logger = logging.getLogger(__name__)

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

@dataclass
class LLMOutputConsumer:
    function_name: str
    location: str
    operation: str
    context: Dict[str, Any] = field(default_factory=dict)

class DataFlowType(Enum):
    ASSIGNMENT = "assignment"
    FUNCTION_CALL = "function_call"
    ATTRIBUTE_ACCESS = "attribute_access"
    SUBSCRIPT_ACCESS = "subscript_access"
    COMPARISON = "comparison"
    ITERATION = "iteration"
    CONDITIONAL = "conditional"
    RETURN = "return"

@dataclass
class DataFlowNode:
    node_id: str
    node_type: DataFlowType
    location: str  # file:line:column
    operation: str
    input_vars: List[str] = field(default_factory=list)
    output_vars: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    is_core_functionality: bool = True

@dataclass
class DataFlowPath:
    path_id: str
    nodes: List[DataFlowNode] = field(default_factory=list)
    start_variable: str = ""
    end_operations: List[str] = field(default_factory=list)
    confidence: float = 1.0

class DataFlowAnalyzer:
    
    def __init__(self, call_graph: Any):
        self.call_graph = call_graph
        self.data_flow_graph = nx.DiGraph() if nx else SimpleDiGraph()
        self.data_flow_nodes = collections.defaultdict(list)
        self.variable_dependencies = collections.defaultdict(set)
        self.llm_output_variables = set()
        self.consumption_points = []
        self.duc_analyzer = beniget.DefUseChains() if beniget else None
        
    def analyze_data_flow(self, 
                         target_directory: str,
                         llm_api_patterns: List[str] = None) -> Dict[str, List[DataFlowPath]]:

        logger.info("Starting data flow analysis")
        
        # Use improved LLM API patterns
        if llm_api_patterns is None:
            llm_api_patterns = self._get_enhanced_llm_patterns()
        
        self._identify_llm_output_variables(target_directory, llm_api_patterns)
        
        self._build_data_flow_graph(target_directory)
        
        data_flow_paths = self._trace_data_flow_paths()
        
        self._identify_consumption_points(data_flow_paths)
        
        logger.info(f"Data flow analysis complete: {len(data_flow_paths)} paths found")
        return data_flow_paths
    
    def _get_enhanced_llm_patterns(self) -> List[str]:

        return [
            'openai', 'gpt', 'chatgpt', 'ChatCompletion', 'Completion',
            'ChatOpenAI', 'AzureChatOpenAI', 'openai_call', 'llm_call',
            'openai.chat.completions', 'openai.completions',
            
            'claude', 'anthropic', 'ChatAnthropic', 'Anthropic',
            'anthropic_client', 'anthropic.messages', 'messages.create',
            
            'gemini', 'genai', 'GenerativeModel', 'google.generativeai',
            'chat_session', 'send_message',
            
            'llm', 'language_model', 'chat_model', 'generate', 'complete',
            'BaseChatModel', 'LLMClient', 'LLMEndpoint', 'create_llm',
            
            'huggingface', 'together', 'cohere', 'replicate', 'palm',
            'llama', 'mistral', 'qianfan', 'tongyi', 'baichuan',
            'TogetherLLM', 'HuggingFaceLLM', 'QianfanChatEndpoint',


            'chat', 'completion', 'embedding', 'model', 'api', 'client',
            'messages.create', 'chat.completions', 'completions.create',
            
            'api_request', 'webhook_request', 'send_message', 'ask_question',
            'get_response', 'generate_text', 'chat_completion', 'ask',
            'get_llm', 'create_chat_model', 'llm_generate'
        ]
    
    def _identify_llm_output_variables(self, target_directory: str, llm_api_patterns: List[str]):

        logger.debug("Identifying LLM output variables")
        
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
                visitor = LLMOutputVariableVisitor(file_path, llm_api_patterns)
                visitor.visit(tree)
                
                # Collect LLM output variables
                self.llm_output_variables.update(visitor.llm_output_vars)
                
            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {e}")
                continue
    
    def _build_data_flow_graph(self, target_directory: str):

        logger.debug("Building data flow graph")
        
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
                visitor = DataFlowGraphVisitor(file_path, self.llm_output_variables)
                visitor.visit(tree)
                
                for var, nodes in visitor.data_flow_nodes.items():
                    self.data_flow_nodes[var].extend(nodes)
                
                for var, deps in visitor.variable_dependencies.items():
                    self.variable_dependencies[var].update(deps)
                    
            except Exception as e:
                logger.warning(f"Failed to build data flow for {file_path}: {e}")
                continue
    
    def _trace_data_flow_paths(self) -> Dict[str, List[DataFlowPath]]:

        logger.debug("Tracing data flow paths")
        
        data_flow_paths = {}
        
        for llm_var in self.llm_output_variables:
            paths = self._trace_paths_for_variable(llm_var)
            if paths:
                data_flow_paths[llm_var] = paths
        
        return data_flow_paths
    
    def _trace_paths_for_variable(self, start_var: str) -> List[DataFlowPath]:

        paths = []
        visited = set()
        
        def explore_path(current_var: str, current_path: List[DataFlowNode], path_id: str):
            if current_var in visited:
                return
            
            visited.add(current_var)
            
            nodes = self.data_flow_nodes.get(current_var, [])
            
            for node in nodes:
                new_path = current_path + [node]
                
                # Check if this is a consumption point
                if self._is_consumption_point(node):
                    path = DataFlowPath(
                        path_id=f"{path_id}_{len(paths)}",
                        nodes=new_path,
                        start_variable=start_var,
                        end_operations=[node.operation],
                        confidence=self._calculate_path_confidence(new_path)
                    )
                    paths.append(path)
                
                for output_var in node.output_vars:
                    if output_var != current_var:  # Avoid cycles
                        explore_path(output_var, new_path, path_id)
        
        explore_path(start_var, [], f"path_{start_var}")
        return paths
    
    def _identify_consumption_points(self, data_flow_paths: Dict[str, List[DataFlowPath]]):

        logger.debug("Identifying consumption points")
        
        for var, paths in data_flow_paths.items():
            for path in paths:
                for node in path.nodes:
                    if self._is_consumption_point(node) and node.is_core_functionality:
                        consumption_info = {
                            'variable': var,
                            'location': node.location,
                            'operation': node.operation,
                            'operation_type': node.node_type.value,
                            'context': node.context,
                            'confidence': path.confidence
                        }
                        self.consumption_points.append(consumption_info)
    
    def _is_consumption_point(self, node: DataFlowNode) -> bool:

        consumption_patterns = [
            'json.loads', '.json()', 'yaml.load', 'xml.etree', 'BeautifulSoup',
            '.split(', '.strip(', '.replace(', '.format(', '.join(',
            'ast.parse', 'compile(', 'exec(', 'eval(',
            'open(', '.write(', '.read(',
            '==', '!=', 'in', 'not in',
            'for', 'while', 'enumerate',
            'print(', 'len(', 'str(', 'int(', 'float('
        ]
        
        operation = node.operation.lower()
        return any(pattern in operation for pattern in consumption_patterns)
    
    def _calculate_path_confidence(self, path: List[DataFlowNode]) -> float:

        if not path:
            return 0.0
        
        base_confidence = 1.0
        
        # Reduce confidence for complex paths
        complexity_penalty = min(0.1 * len(path), 0.5)
        
        # Reduce confidence for non-core functionality
        non_core_penalty = sum(0.1 for node in path if not node.is_core_functionality)
        
        # Reduce confidence for uncertain operations
        uncertain_penalty = sum(0.05 for node in path if 'unknown' in node.operation)
        
        final_confidence = base_confidence - complexity_penalty - non_core_penalty - uncertain_penalty
        return max(final_confidence, 0.1)  # Minimum confidence
    
    def get_consumption_points(self) -> List[Dict[str, Any]]:
        return self.consumption_points
    
    def get_variable_dependencies(self) -> Dict[str, Set[str]]:
        return dict(self.variable_dependencies)


class LLMOutputVariableVisitor(ast.NodeVisitor):
    
    def __init__(self, file_path: str, llm_api_patterns: List[str]):
        self.file_path = file_path
        self.llm_api_patterns = llm_api_patterns
        self.llm_output_vars = set()
        self.current_function = None
    
    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call):
            call_name = self._get_call_name(node.value)
            if call_name and self._is_llm_api_call(call_name):
           
                for target in node.targets:
                    var_names = self._extract_variable_names(target)
                    self.llm_output_vars.update(var_names)
        
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
        return "unknown"
    
    def _is_llm_api_call(self, call_name: str) -> bool:
        return any(pattern in call_name.lower() for pattern in self.llm_api_patterns)
    
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


class DataFlowGraphVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, llm_output_variables: Set[str]):
        self.file_path = file_path
        self.llm_output_variables = llm_output_variables
        self.llm_derived_variables = set(llm_output_variables)
        self.data_flow_nodes = collections.defaultdict(list)
        self.variable_dependencies = collections.defaultdict(set)
        self.current_function = None
        self.current_line = 0
    
    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_Assign(self, node):
        self.current_line = node.lineno
        
        input_vars = self._extract_used_variables(node.value)
        
        output_vars = set()
        for target in node.targets:
            output_vars.update(self._extract_variable_names(target))
        
        if any(var in self.llm_derived_variables for var in input_vars.union(output_vars)):
            data_flow_node = DataFlowNode(
                node_id=f"{self.file_path}:{node.lineno}:{node.col_offset}",
                node_type=DataFlowType.ASSIGNMENT,
                location=f"{self.file_path}:{node.lineno}:{node.col_offset}",
                operation=ast.unparse(node) if hasattr(ast, 'unparse') else str(node),
                input_vars=list(input_vars),
                output_vars=list(output_vars),
                context={'function': self.current_function},
                is_core_functionality=self._is_core_functionality(node)
            )
            
            for var in input_vars.union(output_vars):
                self.data_flow_nodes[var].append(data_flow_node)
            
            for output_var in output_vars:
                self.variable_dependencies[output_var].update(input_vars)
                

            if any(var in self.llm_derived_variables for var in input_vars):
                self.llm_derived_variables.update(output_vars)
        
        self.generic_visit(node)
    
    def visit_Call(self, node):
        self.current_line = node.lineno
        
        input_vars = set()
        for arg in node.args:
            input_vars.update(self._extract_used_variables(arg))
        for keyword in node.keywords:
            input_vars.update(self._extract_used_variables(keyword.value))
        
        if any(var in self.llm_derived_variables for var in input_vars):
            call_name = self._get_call_name(node)
            
            data_flow_node = DataFlowNode(
                node_id=f"{self.file_path}:{node.lineno}:{node.col_offset}",
                node_type=DataFlowType.FUNCTION_CALL,
                location=f"{self.file_path}:{node.lineno}:{node.col_offset}",
                operation=call_name or "unknown_call",
                input_vars=list(input_vars),
                output_vars=[],  
                context={'function': self.current_function, 'call_name': call_name},
                is_core_functionality=self._is_core_functionality(node)
            )
            
            for var in input_vars:
                self.data_flow_nodes[var].append(data_flow_node)
        
        self.generic_visit(node)
    
    def visit_Compare(self, node):
        self.current_line = node.lineno
        
        input_vars = self._extract_used_variables(node.left)
        for comparator in node.comparators:
            input_vars.update(self._extract_used_variables(comparator))
        
        if any(var in self.llm_derived_variables for var in input_vars):
            data_flow_node = DataFlowNode(
                node_id=f"{self.file_path}:{node.lineno}:{node.col_offset}",
                node_type=DataFlowType.COMPARISON,
                location=f"{self.file_path}:{node.lineno}:{node.col_offset}",
                operation=ast.unparse(node) if hasattr(ast, 'unparse') else str(node),
                input_vars=list(input_vars),
                output_vars=[],
                context={'function': self.current_function},
                is_core_functionality=self._is_core_functionality(node)
            )
            
            for var in input_vars:
                self.data_flow_nodes[var].append(data_flow_node)
        
        self.generic_visit(node)
    
    def _extract_used_variables(self, node) -> Set[str]:
        var_names = set()
        
        if isinstance(node, ast.Name):
            var_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            var_names.update(self._extract_used_variables(node.value))
        elif isinstance(node, ast.Subscript):
            var_names.update(self._extract_used_variables(node.value))
            var_names.update(self._extract_used_variables(node.slice))
        elif isinstance(node, ast.Call):
            var_names.update(self._extract_used_variables(node.func))
            for arg in node.args:
                var_names.update(self._extract_used_variables(arg))
            for keyword in node.keywords:
                var_names.update(self._extract_used_variables(keyword.value))
        elif isinstance(node, ast.BinOp):
            var_names.update(self._extract_used_variables(node.left))
            var_names.update(self._extract_used_variables(node.right))
        elif isinstance(node, ast.UnaryOp):
            var_names.update(self._extract_used_variables(node.operand))
        elif isinstance(node, ast.Compare):
            var_names.update(self._extract_used_variables(node.left))
            for comparator in node.comparators:
                var_names.update(self._extract_used_variables(comparator))
        elif isinstance(node, (ast.List, ast.Tuple)):
            for elt in node.elts:
                var_names.update(self._extract_used_variables(elt))
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if key:  # key can be None for **kwargs
                    var_names.update(self._extract_used_variables(key))
            for value in node.values:
                var_names.update(self._extract_used_variables(value))
        
        return var_names
    
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
        return "unknown"
    
    def _is_core_functionality(self, node) -> bool:
        try:
            if hasattr(ast, 'unparse'):
                source = ast.unparse(node).lower()
            else:
                source = str(node).lower()
            
            if any(keyword in source for keyword in ['except', 'error', 'fail', 'catch', 'raise']):
                return False
            
            if any(keyword in source for keyword in ['log', 'debug', 'print', 'warn', 'info']):
                return False
            
            if any(keyword in source for keyword in ['test', 'assert', 'mock']):
                return False
                
            return True
        except:
            return True  
