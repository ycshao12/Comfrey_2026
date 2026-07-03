# Comfrey artifact source file.
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
    require_bytecode_module: bool = False
    enable_langchain_adapter: bool = True
    max_repair_iterations: int = 3  
    repair_iteration_limit: int = 3  
    
    similarity_threshold: float = 0.7  
    enable_embedding_similarity: bool = True 
    embedding_model_size: str = "0.6B"  
    embedding_provider: str = "local"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_model_path: Optional[str] = None
    api_base_url: Optional[str] = None
    api_base_url_env: str = "OPENAI_COMPAT_BASE_URL"
    api_base_url_file: Optional[str] = "../api_url.txt"
    api_key: Optional[str] = None
    api_key_env: str = "OPENAI_COMPAT_API_KEY"
    api_key_file: Optional[str] = "../key.txt"
    api_timeout_seconds: float = 60.0
    embedding_endpoint: str = "/v1/embeddings"
    chat_provider: str = "none"
    chat_model_name: str = "gpt-4.1-mini"
    chat_completion_endpoint: str = "/v1/chat/completions"
    chat_temperature: float = 0.0
    chat_max_tokens: int = 2048
    strict_paper_mode: bool = False
    allow_lightweight_fallbacks: bool = True
    translator_command: Optional[List[str]] = None
    grammar_checker_command: Optional[List[str]] = None
    
    
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

        if self.api_timeout_seconds <= 0:
            raise ValueError("api_timeout_seconds must be positive")

        if self.chat_max_tokens <= 0:
            raise ValueError("chat_max_tokens must be positive")
    
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

    @classmethod
    def create_paper_config(cls) -> 'ComfreyConfig':
        """Create the configuration matching the ICSE paper method."""
        return cls(
            enable_format_detection=True,
            enable_syntax_detection=True,
            enable_repetition_detection=True,
            enable_embedding_similarity=True,
            embedding_provider="openai_compatible",
            embedding_model_name="text-embedding-ada-002",
            embedding_model_size="0.6B",
            chat_provider="openai_compatible",
            chat_model_name="gpt-4.1-mini",
            strict_paper_mode=True,
            allow_lightweight_fallbacks=False,
            history_window_size=10,
            max_repair_iterations=3,
            repair_iteration_limit=3,
            similarity_threshold=0.7,
            element_threshold=3,
            enable_ast_analysis=True,
            enable_bytecode_analysis=True,
            require_bytecode_module=True,
            enable_langchain_adapter=True,
            enable_unicode_detection=True,
            enable_ngram_analysis=True,
            enable_language_standard_check=True,
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
