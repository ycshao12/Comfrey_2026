from dataclasses import dataclass
from typing import Dict, Any, Optional, List

@dataclass
class ComfreyConfig:
    enable_format_detection: bool = True
    enable_syntax_detection: bool = True
    enable_repetition_detection: bool = True
    
    history_window_size: int = 10  
    enable_repair_caching: bool = True
    
    element_threshold: int = 3 
    enable_fsa_validation: bool = True 
    enable_code_fenced_templates: bool = True  
    
    enable_ast_analysis: bool = True  
    enable_bytecode_analysis: bool = True
    max_repair_iterations: int = 3  
    repair_iteration_limit: int = 3  
    
    similarity_threshold: float = 0.7  
    enable_embedding_similarity: bool = True 
    embedding_model_size: str = "0.6B"  
    
    
    enable_lightweight_coherence: bool = True  
    bottom_quartile_threshold: float = 0.25  
    
    internal_redundancy_threshold: float = 0.7  
    contextual_redundancy_threshold: float = 0.4  
    
    coherence_alpha: float = 0.7  
    coherence_beta: float = 0.6  
    coherence_gamma: float = 0.4  
    
    content_overlap_threshold: float = 0.7  
    
    enable_early_termination: bool = True  
    max_processing_time_ms: int = 1000
    
    log_level: str = "INFO"
    enable_detailed_logging: bool = False
    save_repair_history: bool = True
    
    enable_unicode_detection: bool = True  
    enable_ngram_analysis: bool = True  
    enable_language_standard_check: bool = True  
    
    history_queue_size: int = 10  
    deterministic_function_patterns: List[str] = None  
    non_deterministic_function_patterns: List[str] = None  
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.deterministic_function_patterns is None:
            self.deterministic_function_patterns = [
                'read', 'parse', 'fetch', 'get', 'load', 'extract', 'validate',
                'search', 'query', 'find', 'lookup', 'retrieve'
            ]
        
        if self.non_deterministic_function_patterns is None:
            self.non_deterministic_function_patterns = [
                'random', 'time', 'date', 'uuid', 'generate', 'create', 'write',
                'update', 'delete', 'modify', 'save', 'store'
            ]
        
        if not (0.0 <= self.similarity_threshold <= 1.0):
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        
        if not (0.0 <= self.bottom_quartile_threshold <= 1.0):
            raise ValueError("bottom_quartile_threshold must be between 0.0 and 1.0")
        
        if not (0.0 <= self.internal_redundancy_threshold <= 1.0):
            raise ValueError("internal_redundancy_threshold must be between 0.0 and 1.0")
        
        if not (0.0 <= self.contextual_redundancy_threshold <= 1.0):
            raise ValueError("contextual_redundancy_threshold must be between 0.0 and 1.0")
        
        if not (0.0 <= self.content_overlap_threshold <= 1.0):
            raise ValueError("content_overlap_threshold must be between 0.0 and 1.0")
        
        if not (0.0 <= self.coherence_alpha <= 1.0):
            raise ValueError("coherence_alpha must be between 0.0 and 1.0")
        
        if not (0.0 <= self.coherence_beta <= 1.0):
            raise ValueError("coherence_beta must be between 0.0 and 1.0")
        
        if not (0.0 <= self.coherence_gamma <= 1.0):
            raise ValueError("coherence_gamma must be between 0.0 and 1.0")
    
    @classmethod
    def create_lightweight_config(cls) -> 'ComfreyConfig':
        """Create a lightweight configuration for minimal overhead as described in paper"""
        return cls(
            enable_embedding_similarity=False,  
            enable_detailed_logging=False,
            history_window_size=5,
            max_repair_iterations=3,
            enable_lightweight_coherence=True,  
            max_processing_time_ms=500  
        )
    
    @classmethod  
    def create_comprehensive_config(cls) -> 'ComfreyConfig':
        """Create a comprehensive configuration for maximum detection capability"""
        return cls(
            enable_format_detection=True,
            enable_syntax_detection=True,
            enable_repetition_detection=True,
            enable_embedding_similarity=True,  
            enable_detailed_logging=True,
            history_window_size=20,
            max_repair_iterations=5,
            save_repair_history=True
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            field.name: getattr(self, field.name) 
            for field in self.__dataclass_fields__.values()
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ComfreyConfig':
        """Create configuration from dictionary"""
        return cls(**config_dict) 