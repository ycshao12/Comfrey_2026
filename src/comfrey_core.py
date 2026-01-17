import ast
import dis
import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
from .types import ErrorType, DetectionResult, RepairResult
from .config import ComfreyConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComfreyFramework:
    
    def __init__(self, config: ComfreyConfig = None, target_directory: str = None):
        self.config = config or ComfreyConfig()
        self.target_directory = target_directory
        
        from .format_detector import FormatDetector
        from .syntax_detector import SyntaxDetector  
        from .repetition_detector import RepetitionDetector
        from .format_repairer import FormatRepairer
        from .syntax_repairer import SyntaxRepairer
        from .repetition_repairer import RepetitionRepairer
        
        self.format_detector = FormatDetector(self.config)
        self.syntax_detector = SyntaxDetector(self.config)
        self.repetition_detector = RepetitionDetector(self.config)
        
        self.format_repairer = FormatRepairer(self.config)
        self.syntax_repairer = SyntaxRepairer(self.config)
        self.repetition_repairer = RepetitionRepairer(self.config)
        
        from requirement_extraction import RequirementExtractor, PatternAnalyzer, ScenarioRequirementManager
        self.requirement_extractor = RequirementExtractor(self.config)
        self.pattern_analyzer = PatternAnalyzer()
        self.scenario_manager = ScenarioRequirementManager()
        
        self.extracted_requirements = None
        self.requirement_validators = {}
        
        self.execution_history = deque(maxlen=self.config.history_window_size)
        
        self.stats = {
            'total_invocations': 0,
            'format_errors_detected': 0,
            'syntax_errors_detected': 0,
            'repetition_errors_detected': 0,
            'repairs_attempted': 0,
            'repairs_successful': 0,
            'requirements_extracted': 0,
            'dynamic_adaptations': 0
        }
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            self.stats['total_invocations'] += 1
            
            try:
                ai_output = func(*args, **kwargs)
                logger.debug(f"AI function {func.__name__} returned: {ai_output}")
                
                processed_output = self._process_ai_output(ai_output, func.__name__, args, kwargs)
                
                self._update_execution_history(func.__name__, args, kwargs, ai_output, processed_output)
                
                return processed_output
                
            except Exception as e:
                logger.error(f"Error in AI function {func.__name__}: {str(e)}")
                raise
        
        return wrapper
    
    def _process_ai_output(self, ai_output: Any, func_name: str, args: tuple, kwargs: dict) -> Any:
        current_output = ai_output
        repair_log = []
        
        if self.config.enable_format_detection:
            format_results = self._detect_format_errors(current_output, func_name, args, kwargs)
            if any(result.detected for result in format_results):
                self.stats['format_errors_detected'] += len([r for r in format_results if r.detected])
                repaired_output, format_repairs = self._repair_format_errors(current_output, format_results)
                if repaired_output != current_output:
                    current_output = repaired_output
                    repair_log.extend(format_repairs)
                    self.stats['repairs_attempted'] += 1
                    logger.info(f"Format repairs applied: {format_repairs}")
        
        if self.config.enable_syntax_detection:
            syntax_results = self._detect_syntax_errors(current_output, func_name, args, kwargs)
            if any(result.detected for result in syntax_results):
                self.stats['syntax_errors_detected'] += len([r for r in syntax_results if r.detected])
                repaired_output, syntax_repairs = self._repair_syntax_errors(current_output, syntax_results)
                if repaired_output != current_output:
                    current_output = repaired_output
                    repair_log.extend(syntax_repairs)
                    self.stats['repairs_attempted'] += 1
                    logger.info(f"Syntax repairs applied: {syntax_repairs}")
        
        if self.config.enable_repetition_detection:
            repetition_results = self._detect_repetition_errors(current_output, func_name, args, kwargs)
            if any(result.detected for result in repetition_results):
                self.stats['repetition_errors_detected'] += len([r for r in repetition_results if r.detected])
                repaired_output, repetition_repairs = self._repair_repetition_errors(current_output, repetition_results)
                if repaired_output != current_output:
                    current_output = repaired_output
                    repair_log.extend(repetition_repairs)
                    self.stats['repairs_attempted'] += 1
                    logger.info(f"Repetition repairs applied: {repetition_repairs}")
        
        if repair_log:
            self.stats['repairs_successful'] += 1
            logger.info(f"Applied repairs to {func_name}: {repair_log}")
        
        return current_output
    
    def extract_requirements_from_codebase(self, 
                                         target_directory: str = None,
                                         entry_functions: List[str] = None):
        
        if not target_directory:
            target_directory = self.target_directory
            
        if not target_directory:
            logger.warning("No target directory specified for requirement extraction")
            return None
        
        logger.info(f"Extracting requirements from codebase: {target_directory}")
        
       
        extraction_result = self.requirement_extractor.extract_requirements_from_codebase(
            target_directory, entry_functions
        )
        
        from requirement_extraction import DataFlowAnalyzer
        data_flow_analyzer = DataFlowAnalyzer(extraction_result.call_graph)
        llm_api_patterns = ['openai', 'gpt', 'claude', 'llm', 'generate', 'complete']
        
        data_flow_paths = data_flow_analyzer.analyze_data_flow(
            target_directory, llm_api_patterns
        )
        
        self.extracted_requirements = {
            'format': {
                'template_discrepancy': self._extract_template_requirements(data_flow_paths),
                'improper_data_segmentation': self._extract_segmentation_requirements(data_flow_paths),
                'incorrect_context_construction': self._extract_context_requirements(data_flow_paths)
            },
            'syntax': {
                'syntax_parser_misalignment': self._extract_syntax_requirements(data_flow_paths),
                'inconsistent_lexical_features': self._extract_lexical_requirements(data_flow_paths)
            },
            'repetition': {
                'redundant_software_behavior': self._extract_behavior_requirements(data_flow_paths),
                'redundant_semantics': self._extract_semantic_requirements(data_flow_paths)
            }
        }
        
        scenario_requirements = self.scenario_manager.get_scenario_requirements(target_directory)
        self.extracted_requirements['scenario'] = scenario_requirements
        
        expected_scenario_requirements = [
            'intact_textual_elements',  
            'content_relevance',       
            'consistent_lexical_features',  
            'no_redundant_software_behavior', 
            'succinct_content',         
            'contextual_semantic_redundancy'  
        ]
        
        self.stats['requirements_extracted'] = len(self.extracted_requirements)
        logger.info(f"Extracted {self.stats['requirements_extracted']} requirement categories")
        
        return self.extracted_requirements
    
    def _extract_template_requirements(self, data_flow_paths: List[Dict]) -> List[Dict]:
        template_requirements = []
        
        for path in data_flow_paths:
            parsing_patterns = [
                r'json\.loads', r'xml\.etree', r're\.match', r're\.search',
                r'parse', r'extract', r'template', r'format'
            ]
            
            for pattern in parsing_patterns:
                if re.search(pattern, str(path.get('code', '')), re.IGNORECASE):
                    template_requirements.append({
                        'type': 'positional_template',
                        'source': path.get('file', ''),
                        'line': path.get('line', 0),
                        'pattern': pattern,
                        'expected_format': self._infer_template_format(path)
                    })
        
        return template_requirements
    
    def _extract_segmentation_requirements(self, data_flow_paths: List[Dict]) -> List[Dict]:
        segmentation_requirements = []
        
        for path in data_flow_paths:
            chunking_patterns = [
                r'split', r'chunk', r'segment', r'window', r'size',
                r'len\(', r'text\[', r'paragraph', r'sentence'
            ]
            
            for pattern in chunking_patterns:
                if re.search(pattern, str(path.get('code', '')), re.IGNORECASE):
                    segmentation_requirements.append({
                        'type': 'data_segmentation',
                        'source': path.get('file', ''),
                        'line': path.get('line', 0),
                        'pattern': pattern,
                        'chunk_size': self._infer_chunk_size(path),
                        'boundary_markers': self._infer_boundary_markers(path)
                    })
        
        return segmentation_requirements
    
    def _extract_context_requirements(self, data_flow_paths: List[Dict]) -> List[Dict]:
        context_requirements = []
        
        for path in data_flow_paths:
            rag_patterns = [
                r'retrieve', r'search', r'query', r'context', r'embedding',
                r'vector', r'similarity', r'rank', r'rerank'
            ]
            
            for pattern in rag_patterns:
                if re.search(pattern, str(path.get('code', '')), re.IGNORECASE):
                    context_requirements.append({
                        'type': 'context_construction',
                        'source': path.get('file', ''),
                        'line': path.get('line', 0),
                        'pattern': pattern,
                        'relevance_threshold': 0.7,  
                        'similarity_method': 'tfidf_cosine'
                    })
        
        return context_requirements
    
    def _extract_syntax_requirements(self, data_flow_paths: List[Dict]) -> List[Dict]:
        syntax_requirements = []
        
        for path in data_flow_paths:
            syntax_patterns = [
                r'compile', r'ast\.parse', r'eval', r'exec', r'code',
                r'parser', r'lexer', r'token', r'syntax'
            ]
            
            for pattern in syntax_patterns:
                if re.search(pattern, str(path.get('code', '')), re.IGNORECASE):
                    syntax_requirements.append({
                        'type': 'syntax_parser_misalignment',
                        'source': path.get('file', ''),
                        'line': path.get('line', 0),
                        'pattern': pattern,
                        'language': self._infer_programming_language(path),
                        'parser_type': self._infer_parser_type(path)
                    })
        
        return syntax_requirements
    
    def _extract_lexical_requirements(self, data_flow_paths: List[Dict]) -> List[Dict]:
        lexical_requirements = []
        
        for path in data_flow_paths:
            lexical_patterns = [
                r'language', r'locale', r'encoding', r'unicode',
                r'translate', r'localize', r'format', r'style'
            ]
            
            for pattern in lexical_patterns:
                if re.search(pattern, str(path.get('code', '')), re.IGNORECASE):
                    lexical_requirements.append({
                        'type': 'inconsistent_lexical_features',
                        'source': path.get('file', ''),
                        'line': path.get('line', 0),
                        'pattern': pattern,
                        'features': ['language_usage', 'language_standard', 'text_structure']
                    })
        
        return lexical_requirements
    
    def _extract_behavior_requirements(self, data_flow_paths: List[Dict]) -> List[Dict]:
        behavior_requirements = []
        
        for path in data_flow_paths:
            behavior_patterns = [
                r'def ', r'function', r'call', r'invoke', r'execute',
                r'tool', r'api', r'request', r'http'
            ]
            
            for pattern in behavior_patterns:
                if re.search(pattern, str(path.get('code', '')), re.IGNORECASE):
                    behavior_requirements.append({
                        'type': 'redundant_software_behavior',
                        'source': path.get('file', ''),
                        'line': path.get('line', 0),
                        'pattern': pattern,
                        'history_window': 10,  
                        'deterministic_check': True
                    })
        
        return behavior_requirements
    
    def _extract_semantic_requirements(self, data_flow_paths: List[Dict]) -> List[Dict]:
        semantic_requirements = []
        
        for path in data_flow_paths:
            semantic_patterns = [
                r'content', r'text', r'response', r'output', r'generate',
                r'duplicate', r'redundant', r'similar', r'unique'
            ]
            
            for pattern in semantic_patterns:
                if re.search(pattern, str(path.get('code', '')), re.IGNORECASE):
                    semantic_requirements.append({
                        'type': 'redundant_semantics',
                        'source': path.get('file', ''),
                        'line': path.get('line', 0),
                        'pattern': pattern,
                        'similarity_threshold': 0.7,  
                        'detection_method': 'two_stage_similarity'
                    })
        
        return semantic_requirements
    
    def _infer_template_format(self, path: Dict) -> str:
        code = str(path.get('code', ''))
        
        if 'json' in code.lower():
            return 'json'
        elif 'xml' in code.lower():
            return 'xml'
        elif 'yaml' in code.lower():
            return 'yaml'
        elif 'csv' in code.lower():
            return 'csv'
        else:
            return 'text'
    
    def _infer_chunk_size(self, path: Dict) -> int:
        code = str(path.get('code', ''))
        
        size_match = re.search(r'size\s*=\s*(\d+)', code)
        if size_match:
            return int(size_match.group(1))
        
        return 1000
    
    def _infer_boundary_markers(self, path: Dict) -> List[str]:
        code = str(path.get('code', ''))
        markers = []
        
        if 'sentence' in code.lower():
            markers.append('.')
        if 'paragraph' in code.lower():
            markers.append('\n\n')
        if 'word' in code.lower():
            markers.append(' ')
        
        return markers if markers else ['.', '\n']
    
    def _infer_programming_language(self, path: Dict) -> str:
        file_path = path.get('file', '')
        
        if file_path.endswith('.py'):
            return 'python'
        elif file_path.endswith('.js'):
            return 'javascript'
        elif file_path.endswith('.java'):
            return 'java'
        elif file_path.endswith('.cpp') or file_path.endswith('.cc'):
            return 'cpp'
        else:
            return 'unknown'
    
    def _infer_parser_type(self, path: Dict) -> str:
        code = str(path.get('code', ''))
        
        if 'ast.parse' in code:
            return 'ast_parser'
        elif 'compile' in code:
            return 'compiler'
        elif 'eval' in code:
            return 'interpreter'
        else:
            return 'unknown'
    
    def adapt_detection_to_requirements(self, output: Any, func_name: str, context: Dict[str, Any] = None):
        if not self.extracted_requirements:
            logger.debug("No extracted requirements available, using default detection")
            return []
        
        self.stats['dynamic_adaptations'] += 1
        
        output_type = self._infer_output_type(output)
        applicable_requirements = self.scenario_manager.get_applicable_requirements(
            context or {}, output_type
        )
        
        validation_results = []
        for requirement in applicable_requirements:
            if requirement.name in self.requirement_validators:
                validator = self.requirement_validators[requirement.name]
                result = validator(output, context)
                validation_results.append(result)
        
        detection_results = []
        for validation in validation_results:
            if not validation['passed']:
                detection_result = DetectionResult(
                    error_type=self._map_requirement_to_error_type(validation['requirement_name']),
                    detected=True,
                    severity=1.0 - validation['confidence'],
                    details={
                        'requirement_name': validation['requirement_name'],
                        'dimension': validation['dimension'],
                        'violations': validation['violations'],
                        'validation_details': validation['details']
                    }
                )
                detection_results.append(detection_result)
        
        return detection_results
    
    def _infer_output_type(self, output: Any) -> str:
        output_str = str(output)
        
        if output_str.strip().startswith(('{', '[')):
            return 'structured'
        
        if any(keyword in output_str for keyword in ['def ', 'class ', 'import ', 'from ']):
            return 'code'
        
        if len(output_str.split()) > 50:  
            return 'context'
        
        return 'text'
    
    def _map_requirement_to_error_type(self, requirement_name: str) -> ErrorType:
        mapping = {
            'intact_textual_elements': ErrorType.FORMAT_DATA_SEGMENTATION,
            'content_relevance': ErrorType.FORMAT_CONTEXT_CONSTRUCTION,
            'cohesive_context_information': ErrorType.FORMAT_CONTEXT_CONSTRUCTION,
            'parser_compatible_grammar': ErrorType.SYNTAX_PARSER_MISALIGNMENT,
            'consistent_lexical_features': ErrorType.SYNTAX_LEXICAL_INCONSISTENCY,
            'no_redundant_software_behavior': ErrorType.REPETITION_SOFTWARE_BEHAVIOR,
            'succinct_content': ErrorType.REPETITION_SEMANTIC_REDUNDANCY
        }
        return mapping.get(requirement_name, ErrorType.FORMAT_TEMPLATE_DISCREPANCY)
    
    def _detect_format_errors(self, output: Any, func_name: str, args: tuple, kwargs: dict) -> List[DetectionResult]:
        results = []
        
        template_result = self.format_detector.detect_template_discrepancy(output, func_name)
        results.append(template_result)
        
        segmentation_result = self.format_detector.detect_data_segmentation_issues(output, func_name)
        results.append(segmentation_result)
        
        context_result = self.format_detector.detect_context_construction_issues(output, func_name)
        results.append(context_result)
        
        return results
    
    def _detect_syntax_errors(self, output: Any, func_name: str, args: tuple, kwargs: dict) -> List[DetectionResult]:
        results = []
        
        parser_result = self.syntax_detector.detect_parser_misalignment(output, func_name)
        results.append(parser_result)
        
        lexical_result = self.syntax_detector.detect_lexical_inconsistency(output, func_name)
        results.append(lexical_result)
        
        return results
    
    def _detect_repetition_errors(self, output: Any, func_name: str, args: tuple, kwargs: dict) -> List[DetectionResult]:
        results = []
        
        behavior_result = self.repetition_detector.detect_software_behavior_redundancy(
            output, func_name, args, kwargs, self.execution_history
        )
        results.append(behavior_result)
        
        semantic_result = self.repetition_detector.detect_semantic_redundancy(
            output, func_name, self.execution_history
        )
        results.append(semantic_result)
        
        return results
    
    def _repair_format_errors(self, output: Any, detection_results: List[DetectionResult]) -> Tuple[Any, List[str]]:
        current_output = output
        repairs = []
        
        for result in detection_results:
            if result.detected:
                if result.error_type == ErrorType.FORMAT_TEMPLATE_DISCREPANCY:
                    repair_result = self.format_repairer.repair_template_discrepancy(current_output, result)
                    if repair_result.success:
                        current_output = repair_result.repaired_output
                        repairs.extend(repair_result.repair_actions)
                
                elif result.error_type == ErrorType.FORMAT_DATA_SEGMENTATION:
                    repair_result = self.format_repairer.repair_data_segmentation(current_output, result)
                    if repair_result.success:
                        current_output = repair_result.repaired_output
                        repairs.extend(repair_result.repair_actions)
                
                elif result.error_type == ErrorType.FORMAT_CONTEXT_CONSTRUCTION:
                    repair_result = self.format_repairer.repair_context_construction(current_output, result)
                    if repair_result.success:
                        current_output = repair_result.repaired_output
                        repairs.extend(repair_result.repair_actions)
        
        return current_output, repairs
    
    def _repair_syntax_errors(self, output: Any, detection_results: List[DetectionResult]) -> Tuple[Any, List[str]]:
        current_output = output
        repairs = []
        
        for result in detection_results:
            if result.detected:
                if result.error_type == ErrorType.SYNTAX_PARSER_MISALIGNMENT:
                    repair_result = self.syntax_repairer.repair_parser_misalignment(current_output, result)
                    if repair_result.success:
                        current_output = repair_result.repaired_output
                        repairs.extend(repair_result.repair_actions)
                
                elif result.error_type == ErrorType.SYNTAX_LEXICAL_INCONSISTENCY:
                    repair_result = self.syntax_repairer.repair_lexical_inconsistency(current_output, result)
                    if repair_result.success:
                        current_output = repair_result.repaired_output
                        repairs.extend(repair_result.repair_actions)
        
        return current_output, repairs
    
    def _repair_repetition_errors(self, output: Any, detection_results: List[DetectionResult]) -> Tuple[Any, List[str]]:
        current_output = output
        repairs = []
        
        for result in detection_results:
            if result.detected:
                if result.error_type == ErrorType.REPETITION_SOFTWARE_BEHAVIOR:
                    repair_result = self.repetition_repairer.repair_software_behavior_redundancy(current_output, result)
                    if repair_result.success:
                        current_output = repair_result.repaired_output
                        repairs.extend(repair_result.repair_actions)
                
                elif result.error_type == ErrorType.REPETITION_SEMANTICS:
                    repair_result = self.repetition_repairer.repair_semantic_redundancy(current_output, result)
                    if repair_result.success:
                        current_output = repair_result.repaired_output
                        repairs.extend(repair_result.repair_actions)
        
        return current_output, repairs
    
    def _repair_dynamic_errors(self, output: Any, detection_results: List[DetectionResult]) -> Tuple[Any, List[str]]:
        current_output = output
        repairs = []
        
        for result in detection_results:
            if result.detected:
                requirement_name = result.details.get('requirement_name', '')
                dimension = result.details.get('dimension', '')
                
                if dimension == 'format':
                    repair_result = self._repair_format_requirement(current_output, result)
                elif dimension == 'syntax':
                    repair_result = self._repair_syntax_requirement(current_output, result)
                elif dimension == 'repetition':
                    repair_result = self._repair_repetition_requirement(current_output, result)
                else:
                    continue
                
                if repair_result.success:
                    current_output = repair_result.repaired_output
                    repairs.append(f"Dynamic repair: {requirement_name}")
        
        return current_output, repairs
    
    def _repair_format_requirement(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        requirement_name = detection_result.details.get('requirement_name', '')
        
        if requirement_name == 'intact_textual_elements':
            return self.format_repairer.repair_data_segmentation_issues(output, detection_result)
        elif requirement_name in ['content_relevance', 'cohesive_context_information']:
            return self.format_repairer.repair_context_construction_issues(output, detection_result)
        else:
            return self.format_repairer.repair_template_discrepancy(output, detection_result)
    
    def _repair_syntax_requirement(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        requirement_name = detection_result.details.get('requirement_name', '')
        
        if requirement_name == 'parser_compatible_grammar':
            return self.syntax_repairer.repair_parser_misalignment(output, detection_result)
        elif requirement_name == 'consistent_lexical_features':
            return self.syntax_repairer.repair_lexical_inconsistency(output, detection_result)
        else:
            return self.syntax_repairer.repair_parser_misalignment(output, detection_result)
    
    def _repair_repetition_requirement(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        requirement_name = detection_result.details.get('requirement_name', '')
        
        if requirement_name == 'no_redundant_software_behavior':
            return self.repetition_repairer.repair_software_behavior_redundancy(output, detection_result)
        elif requirement_name == 'succinct_content':
            return self.repetition_repairer.repair_semantic_redundancy(output, detection_result)
        else:
            return self.repetition_repairer.repair_semantic_redundancy(output, detection_result)
    
    def _update_execution_history(self, func_name: str, args: tuple, kwargs: dict, 
                                 original_output: Any, processed_output: Any):
        entry = {
            'timestamp': __import__('time').time(),
            'function_name': func_name,
            'args': args,
            'kwargs': kwargs,
            'original_output': original_output,
            'processed_output': processed_output
        }
        self.execution_history.append(entry)
    
    def get_statistics(self) -> Dict[str, Any]:
        return self.stats.copy()
    
    def reset_statistics(self):
        self.stats = {
            'total_invocations': 0,
            'format_errors_detected': 0,
            'syntax_errors_detected': 0,
            'repetition_errors_detected': 0,
            'repairs_attempted': 0,
            'repairs_successful': 0,
            'requirements_extracted': 0,
            'dynamic_adaptations': 0
        } 