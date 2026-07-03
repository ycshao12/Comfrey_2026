
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class ScenarioDimension(Enum):
    FORMAT = "format"
    SYNTAX = "syntax"
    REPETITION = "repetition"

@dataclass
class ScenarioRequirement:
    name: str
    dimension: ScenarioDimension
    description: str
    detection_criteria: Dict[str, Any]
    validation_rules: List[str] = field(default_factory=list)
    priority: int = 1  
    applicable_contexts: List[str] = field(default_factory=list)

class ScenarioRequirementManager:
    
    def __init__(self):
        self.scenario_requirements = self._initialize_scenario_requirements()
        
    def get_applicable_requirements(self, 
                                  context: Dict[str, Any],
                                  output_type: str = "general") -> List[ScenarioRequirement]:
        applicable = []
        
        for requirement in self.scenario_requirements:
            if self._is_requirement_applicable(requirement, context, output_type):
                applicable.append(requirement)
        
        applicable.sort(key=lambda req: req.priority)
        
        logger.debug(f"Found {len(applicable)} applicable scenario requirements")
        return applicable
    
    def get_requirements_by_dimension(self, dimension: ScenarioDimension) -> List[ScenarioRequirement]:
        return [req for req in self.scenario_requirements if req.dimension == dimension]
    
    def get_all_requirements(self) -> List[ScenarioRequirement]:
        return self.scenario_requirements.copy()

    def get_scenario_requirements(self, target_directory: str = None) -> List[Dict[str, Any]]:
        """Return the paper's scenario-driven requirements in serializable form."""
        return [
            {
                'name': requirement.name,
                'dimension': requirement.dimension.value,
                'description': requirement.description,
                'detection_criteria': requirement.detection_criteria,
                'validation_rules': requirement.validation_rules,
                'priority': requirement.priority,
                'applicable_contexts': requirement.applicable_contexts,
                'source': 'application_scenario',
                'target_directory': target_directory
            }
            for requirement in self.scenario_requirements
        ]
    
    def _initialize_scenario_requirements(self) -> List[ScenarioRequirement]:
        requirements = []
    
        requirements.append(ScenarioRequirement(
            name="intact_textual_elements",
            dimension=ScenarioDimension.FORMAT,
            description="Text segments must contain complete words at boundaries",
            detection_criteria={
                "check_word_boundaries": True,
                "check_hyphenation": True,
                "check_sentence_fragments": True,
                "boundary_markers": ['.', '!', '?', '\n', '\n\n'],
                "word_completeness_threshold": 0.95
            },
            validation_rules=[
                "No word should be split across segment boundaries",
                "Hyphenated words should be kept together",
                "Sentence fragments should be avoided",
                "Punctuation should be preserved with associated text"
            ],
            priority=1,
            applicable_contexts=["text_processing", "segmentation", "chunking", "rag_systems"]
        ))
        
        requirements.append(ScenarioRequirement(
            name="content_relevance",
            dimension=ScenarioDimension.FORMAT,
            description="Context content must be relevant to the query",
            detection_criteria={
                "relevance_threshold": 0.6,
                "similarity_metric": "cosine",
                "check_topic_alignment": True,
                "check_semantic_coherence": True,
                "max_irrelevant_ratio": 0.3
            },
            validation_rules=[
                "Context segments should be semantically related to the query",
                "Irrelevant content should be filtered out",
                "Topic drift should be minimized",
                "Semantic coherence should be maintained"
            ],
            priority=1,
            applicable_contexts=["rag_systems", "context_construction", "information_retrieval"]
        ))
        
        requirements.append(ScenarioRequirement(
            name="consistent_lexical_features",
            dimension=ScenarioDimension.SYNTAX,
            description="Maintain consistent spelling and language standards",
            detection_criteria={
                "spelling_consistency": True,
                "language_consistency": True,
                "grammar_consistency": True,
                "style_consistency": True,
                "mixed_language_threshold": 0.1
            },
            validation_rules=[
                "Spelling standard should be consistent (US vs UK English)",
                "Language mixing should be avoided unless intentional",
                "Grammar patterns should be uniform",
                "Writing style should be consistent"
            ],
            priority=2,
            applicable_contexts=["text_generation", "document_creation", "content_writing"]
        ))
        
   
        requirements.append(ScenarioRequirement(
            name="no_redundant_software_behavior",
            dimension=ScenarioDimension.REPETITION,
            description="Avoid unnecessary repeated software actions",
            detection_criteria={
                "action_repetition_threshold": 2,
                "identical_parameters": True,
                "deterministic_output": True,
                "temporal_window": 10, 
                "cache_validity": True
            },
            validation_rules=[
                "Identical actions with same parameters should not be repeated",
                "Deterministic operations should be cached",
                "Unnecessary API calls should be avoided",
                "Resource usage should be optimized"
            ],
            priority=2,
            applicable_contexts=["api_calls", "tool_usage", "function_execution", "agent_behavior"]
        ))
        
        requirements.append(ScenarioRequirement(
            name="succinct_content",
            dimension=ScenarioDimension.REPETITION,
            description="Avoid semantic redundancy in content",
            detection_criteria={
                "semantic_similarity_threshold": 0.8,
                "content_overlap_threshold": 0.7,
                "redundancy_detection": True,
                "information_density": 0.6,
                "repetition_penalty": 0.5
            },
            validation_rules=[
                "Semantically similar content should be consolidated",
                "Information should not be unnecessarily repeated",
                "Content should be concise and informative",
                "Redundant phrases should be eliminated"
            ],
            priority=2,
            applicable_contexts=["text_generation", "content_creation", "summarization", "enumeration"]
        ))

        requirements.append(ScenarioRequirement(
            name="contextual_semantic_redundancy",
            dimension=ScenarioDimension.REPETITION,
            description="Avoid responses that semantically repeat the prompt or contextual input",
            detection_criteria={
                "semantic_similarity_threshold": 0.7,
                "check_prompt_response_similarity": True,
                "check_context_response_similarity": True
            },
            validation_rules=[
                "Response should not simply restate the prompt",
                "Response should not duplicate contextual input",
                "Generated content should add new useful information"
            ],
            priority=2,
            applicable_contexts=["text_generation", "rag_systems", "agent_response", "summarization"]
        ))
        
        return requirements
    
    def _is_requirement_applicable(self, 
                                 requirement: ScenarioRequirement,
                                 context: Dict[str, Any],
                                 output_type: str) -> bool:
        
        context_type = context.get('type', 'general')
        application_domain = context.get('domain', 'general')
        
     
        if requirement.applicable_contexts:
            context_match = any(
                ctx in context_type.lower() or 
                ctx in application_domain.lower() or
                ctx in output_type.lower()
                for ctx in requirement.applicable_contexts
            )
            if not context_match:
                return False
        
 
        if requirement.dimension == ScenarioDimension.FORMAT:
           
            return output_type in ['text', 'structured', 'general', 'context']
        
        elif requirement.dimension == ScenarioDimension.SYNTAX:
    
            return output_type in ['code', 'structured', 'general', 'compilation']
        
        elif requirement.dimension == ScenarioDimension.REPETITION:
           
            return True
        
        return True
    
    def create_requirement_validators(self, 
                                   requirements: List[ScenarioRequirement]) -> Dict[str, callable]:
       
        validators = {}
        
        for requirement in requirements:
            validator_name = f"validate_{requirement.name}"
            validator_func = self._create_validator_function(requirement)
            validators[requirement.name] = validator_func
        
        return validators
    
    def _create_validator_function(self, requirement: ScenarioRequirement) -> callable:
       
        def validator(output: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
           
            result = {
                'requirement_name': requirement.name,
                'dimension': requirement.dimension.value,
                'passed': False,
                'confidence': 0.0,
                'violations': [],
                'details': {}
            }
            
            try:
          
                if requirement.name == "intact_textual_elements":
                    result = self._validate_intact_textual_elements(output, requirement, context)
                elif requirement.name == "content_relevance":
                    result = self._validate_content_relevance(output, requirement, context)
                elif requirement.name == "cohesive_context_information":
                    result = self._validate_cohesive_context(output, requirement, context)
                elif requirement.name == "parser_compatible_grammar":
                    result = self._validate_parser_compatibility(output, requirement, context)
                elif requirement.name == "consistent_lexical_features":
                    result = self._validate_lexical_consistency(output, requirement, context)
                elif requirement.name == "no_redundant_software_behavior":
                    result = self._validate_no_redundant_behavior(output, requirement, context)
                elif requirement.name == "succinct_content":
                    result = self._validate_succinct_content(output, requirement, context)
                elif requirement.name == "contextual_semantic_redundancy":
                    result = self._validate_contextual_semantic_redundancy(output, requirement, context)
                else:
                    result['details']['error'] = f"Unknown requirement: {requirement.name}"
                    
            except Exception as e:
                result['details']['error'] = str(e)
                logger.warning(f"Validation error for {requirement.name}: {e}")
            
            return result
        
        return validator
    
    def _validate_intact_textual_elements(self, output: Any, requirement: ScenarioRequirement, context: Dict[str, Any]) -> Dict[str, Any]:

        result = {
            'requirement_name': requirement.name,
            'dimension': requirement.dimension.value,
            'passed': True,
            'confidence': 1.0,
            'violations': [],
            'details': {}
        }
        
        output_str = str(output)
        criteria = requirement.detection_criteria
        
   
        if criteria.get('check_word_boundaries', True):
     
            words = output_str.split()
            if words:
          
                first_word = words[0]
                last_word = words[-1]
                
        
                if first_word.startswith('-') or last_word.endswith('-'):
                    result['violations'].append("Hyphenated word split detected")
                    result['passed'] = False
                
                if not any(output_str.strip().endswith(marker) for marker in criteria.get('boundary_markers', [])):
                    result['violations'].append("Incomplete sentence fragment")
                    result['confidence'] *= 0.8
        
        result['details']['word_count'] = len(output_str.split())
        result['details']['boundary_check'] = len(result['violations']) == 0
        
        return result
    
    def _validate_content_relevance(self, output: Any, requirement: ScenarioRequirement, context: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'requirement_name': requirement.name,
            'dimension': requirement.dimension.value,
            'passed': True,
            'confidence': 0.8,  
            'violations': [],
            'details': {}
        }
        
        if context and 'query' in context:
            query = context['query']
            output_str = str(output)
            
            query_words = set(query.lower().split())
            output_words = set(output_str.lower().split())
            
            overlap_ratio = len(query_words.intersection(output_words)) / len(query_words) if query_words else 0
            
            threshold = requirement.detection_criteria.get('relevance_threshold', 0.6)
            if overlap_ratio < threshold:
                result['violations'].append(f"Low relevance score: {overlap_ratio:.2f}")
                result['passed'] = False
                result['confidence'] = overlap_ratio
            
            result['details']['relevance_score'] = overlap_ratio
        else:
            result['details']['note'] = "No query context provided for relevance check"
        
        return result
    
    def _validate_cohesive_context(self, output: Any, requirement: ScenarioRequirement, context: Dict[str, Any]) -> Dict[str, Any]:

        result = {
            'requirement_name': requirement.name,
            'dimension': requirement.dimension.value,
            'passed': True,
            'confidence': 0.8,
            'violations': [],
            'details': {}
        }
        
        output_str = str(output)
        

        sentences = [s.strip() for s in output_str.split('.') if s.strip()]
        
        if len(sentences) > 1:
            coherence_score = 0.8  
            
            threshold = requirement.detection_criteria.get('coherence_threshold', 0.7)
            if coherence_score < threshold:
                result['violations'].append(f"Low coherence score: {coherence_score:.2f}")
                result['passed'] = False
                result['confidence'] = coherence_score
            
            result['details']['coherence_score'] = coherence_score
            result['details']['sentence_count'] = len(sentences)
        
        return result
    
    def _validate_parser_compatibility(self, output: Any, requirement: ScenarioRequirement, context: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'requirement_name': requirement.name,
            'dimension': requirement.dimension.value,
            'passed': True,
            'confidence': 1.0,
            'violations': [],
            'details': {}
        }
        
        output_str = str(output)
        
        try:
            if output_str.strip().startswith(('{', '[')):
                import json
                json.loads(output_str)
                result['details']['json_valid'] = True
            
            elif any(keyword in output_str for keyword in ['def ', 'class ', 'import ', 'from ']):
                import ast
                ast.parse(output_str)
                result['details']['python_valid'] = True
                
        except (json.JSONDecodeError, SyntaxError) as e:
            result['violations'].append(f"Parser error: {str(e)}")
            result['passed'] = False
            result['confidence'] = 0.0
            result['details']['parse_error'] = str(e)
        
        return result
    
    def _validate_lexical_consistency(self, output: Any, requirement: ScenarioRequirement, context: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'requirement_name': requirement.name,
            'dimension': requirement.dimension.value,
            'passed': True,
            'confidence': 0.9,
            'violations': [],
            'details': {}
        }
        
        output_str = str(output)
        
        us_spellings = ['color', 'center', 'organize', 'realize']
        uk_spellings = ['colour', 'centre', 'organise', 'realise']
        
        us_count = sum(1 for word in us_spellings if word in output_str.lower())
        uk_count = sum(1 for word in uk_spellings if word in output_str.lower())
        
        if us_count > 0 and uk_count > 0:
            result['violations'].append("Mixed spelling standards detected")
            result['passed'] = False
            result['confidence'] = 0.7
        
        result['details']['us_spelling_count'] = us_count
        result['details']['uk_spelling_count'] = uk_count
        
        return result
    
    def _validate_no_redundant_behavior(self, output: Any, requirement: ScenarioRequirement, context: Dict[str, Any]) -> Dict[str, Any]:

        result = {
            'requirement_name': requirement.name,
            'dimension': requirement.dimension.value,
            'passed': True,
            'confidence': 0.8,
            'violations': [],
            'details': {}
        }
        

        result['details']['note'] = "Requires action history for full validation"
        
        return result
    
    def _validate_succinct_content(self, output: Any, requirement: ScenarioRequirement, context: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'requirement_name': requirement.name,
            'dimension': requirement.dimension.value,
            'passed': True,
            'confidence': 0.8,
            'violations': [],
            'details': {}
        }
        
        output_str = str(output)
        
        sentences = [s.strip() for s in output_str.split('.') if s.strip()]
        
        if len(sentences) > 1:
            unique_sentences = set(sentences)
            redundancy_ratio = 1 - (len(unique_sentences) / len(sentences))
            
            threshold = requirement.detection_criteria.get('content_overlap_threshold', 0.7)
            if redundancy_ratio > (1 - threshold):
                result['violations'].append(f"High redundancy ratio: {redundancy_ratio:.2f}")
                result['passed'] = False
                result['confidence'] = 1 - redundancy_ratio
            
            result['details']['redundancy_ratio'] = redundancy_ratio
            result['details']['unique_sentences'] = len(unique_sentences)
            result['details']['total_sentences'] = len(sentences)
        
        return result 

    def _validate_contextual_semantic_redundancy(self, output: Any, requirement: ScenarioRequirement, context: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'requirement_name': requirement.name,
            'dimension': requirement.dimension.value,
            'passed': True,
            'confidence': 0.8,
            'violations': [],
            'details': {}
        }

        context = context or {}
        output_str = str(output)
        prompt_text = (
            context.get('prompt')
            or context.get('query')
            or context.get('user_input')
            or context.get('context_text')
            or ''
        )

        if not prompt_text:
            result['details']['note'] = "No prompt or context text provided for contextual redundancy check"
            return result

        output_words = set(output_str.lower().split())
        prompt_words = set(str(prompt_text).lower().split())
        similarity = (
            len(output_words.intersection(prompt_words)) / len(output_words.union(prompt_words))
            if output_words and prompt_words else 0.0
        )

        threshold = requirement.detection_criteria.get('semantic_similarity_threshold', 0.7)
        if similarity > threshold:
            result['violations'].append(f"High prompt-response similarity: {similarity:.2f}")
            result['passed'] = False
            result['confidence'] = 1 - similarity

        result['details']['contextual_similarity'] = similarity
        return result
