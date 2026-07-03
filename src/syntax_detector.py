# Comfrey artifact source file.

import ast
import dis
import re
import json
import xml.etree.ElementTree as ET
import token
import tokenize
import io
import unicodedata
from typing import Dict, List, Any, Optional, Tuple
import logging

from .types import DetectionResult, ErrorType
from .config import ComfreyConfig

logger = logging.getLogger(__name__)

class SyntaxDetector:

    def __init__(self, config: ComfreyConfig):
        self.config = config
        self.session_language_patterns = {}  
        self.session_spelling_standard = None  
        
    def detect_parser_misalignment(self, output: Any, func_name: str) -> DetectionResult:
       
        try:
            output_str = str(output)
            violations = []
            severity = 0.0

            parser_results = self._run_parser_registry(output_str, func_name)
            if not parser_results:
                return DetectionResult(
                    error_type=ErrorType.SYNTAX_PARSER_MISALIGNMENT,
                    detected=False,
                    severity=0.0,
                    details={"reason": "Output does not appear to target a parser/compiler"}
                )

            successful = [item for item in parser_results if item["success"]]
            if successful:
                return DetectionResult(
                    error_type=ErrorType.SYNTAX_PARSER_MISALIGNMENT,
                    detected=False,
                    severity=0.0,
                    details={
                        "reason": "At least one applicable parser/compiler accepted the output",
                        "parser_results": parser_results,
                        "accepted_by": [item["parser"] for item in successful]
                    }
                )

            for item in parser_results:
                violations.append({
                    'type': 'syntax_error',
                    'parser': item['parser'],
                    'message': item.get('error', 'parser rejected output'),
                })
            severity = 0.8
            
            # Additional AST-based validation for specific error types
            if self.config.enable_ast_analysis:
                ast_issues = self._detect_ast_violations(output_str)
                if ast_issues:
                    violations.extend(ast_issues)
                    severity = min(severity + 0.2, 1.0)
            
            detected = len(violations) > 0
            
            return DetectionResult(
                error_type=ErrorType.SYNTAX_PARSER_MISALIGNMENT,
                detected=detected,
                severity=severity,
                details={
                    "violations": violations,
                    "total_issues": len(violations),
                    "output_length": len(output_str),
                    "detection_method": "multi_parser_registry",
                    "parser_results": parser_results
                },
                suggested_repair="ast_refinement" if detected else None
            )
            
        except Exception as e:
            logger.error(f"Error in syntax detection: {str(e)}")
            return DetectionResult(
                error_type=ErrorType.SYNTAX_PARSER_MISALIGNMENT,
                detected=False,
                severity=0.0,
                details={"error": str(e)}
            )

    def _run_parser_registry(self, text: str, func_name: str = "") -> List[Dict[str, Any]]:
        candidates = self._infer_parser_candidates(text, func_name)
        results = []
        for parser_name in candidates:
            try:
                if parser_name == "python":
                    compile(text, '<string>', 'exec')
                elif parser_name == "json":
                    json.loads(text)
                elif parser_name == "yaml":
                    import yaml
                    yaml.safe_load(text)
                elif parser_name == "xml":
                    ET.fromstring(text)
                elif parser_name == "markdown_code_fence":
                    self._validate_markdown_code_fence(text)
                else:
                    continue
                results.append({"parser": parser_name, "success": True})
            except Exception as exc:
                results.append({"parser": parser_name, "success": False, "error": str(exc)})
        return results

    def _infer_parser_candidates(self, text: str, func_name: str = "") -> List[str]:
        stripped = text.strip()
        lowered_name = func_name.lower()
        if any(token in lowered_name for token in ("json", "schema")):
            return ["json"]
        if any(token in lowered_name for token in ("xml", "html")):
            return ["xml"]
        if any(token in lowered_name for token in ("yaml", "yml")):
            return ["yaml"]
        if any(token in lowered_name for token in ("markdown", "code_fence", "fence")):
            return ["markdown_code_fence"]
        if any(token in lowered_name for token in ("python", "code", "compile", "ast")):
            return ["python"]

        candidates = []
        if stripped.startswith(("{", "[")):
            return ["json"]
        if stripped.startswith("<") and stripped.endswith(">"):
            return ["xml"]
        if stripped.startswith("```") or stripped.count("```") == 1:
            return ["markdown_code_fence"]
        if re.search(r'^\s*[\w.-]+\s*:\s+', stripped, re.MULTILINE):
            return ["yaml"]
        if self._looks_like_code(stripped):
            candidates.append("python")
        return list(dict.fromkeys(candidates))

    def _validate_markdown_code_fence(self, text: str):
        if text.count("```") % 2 != 0:
            raise ValueError("unmatched markdown code fence")
        for match in re.finditer(r'```([^\n`]*)\n', text):
            language = match.group(1).strip()
            if language and not re.match(r'^[A-Za-z0-9_+.-]+$', language):
                raise ValueError(f"invalid code fence language identifier: {language}")
    
    def detect_lexical_inconsistency(self, output: Any, func_name: str) -> DetectionResult:
        
        try:
            output_str = str(output)
            violations = []
            severity = 0.0
            
            # 1. Language usage detection using Unicode script detection
            if self.config.enable_unicode_detection:
                language_issues = self._detect_language_usage_inconsistency(output_str)
                if language_issues:
                    violations.extend(language_issues)
                    severity += 0.4
            
            # 2. Language standard detection using dictionary validation
            if self.config.enable_language_standard_check:
                spelling_issues = self._detect_spelling_standard_inconsistency(output_str)
                if spelling_issues:
                    violations.extend(spelling_issues)
                    severity += 0.3
            
            # 3. Text structure consistency detection
            structure_issues = self._detect_text_structure_inconsistency(output_str)
            if structure_issues:
                violations.extend(structure_issues)
                severity += 0.3
            
            detected = len(violations) > 0
            severity = min(severity, 1.0)
            
            return DetectionResult(
                error_type=ErrorType.SYNTAX_LEXICAL_INCONSISTENCY,
                detected=detected,
                severity=severity,
                details={
                    "violations": violations,
                    "total_issues": len(violations),
                    "session_spelling_standard": self.session_spelling_standard,
                    "detected_languages": self._get_detected_languages(output_str),
                    "detection_method": "unicode_ngram_analysis"
                },
                suggested_repair="lexical_standardization" if detected else None
            )
            
        except Exception as e:
            logger.error(f"Error in lexical detection: {str(e)}")
            return DetectionResult(
                error_type=ErrorType.SYNTAX_LEXICAL_INCONSISTENCY,
                detected=False,
                severity=0.0,
                details={"error": str(e)}
            )
    
    def _looks_like_code(self, text: str) -> bool:
        code_indicators = [
            r'\bdef\s+\w+\s*\(',  # Function definitions
            r'\bclass\s+\w+',     # Class definitions
            r'\bimport\s+\w+',    # Import statements
            r'\bfrom\s+\w+\s+import',  # From imports
            r'[\{\[\(].*[\}\]\)]',     # Brackets
            r'[=+\-*/]',              # Operators
            r';\s*$',                 # Semicolons
            r'^\s*#',                 # Comments
        ]
        
        for pattern in code_indicators:
            if re.search(pattern, text, re.MULTILINE):
                return True
        return False
    
    def _detect_ast_violations(self, text: str) -> List[Dict[str, Any]]:
       
        violations = []
        
        try:
            ast.parse(text)
            
        except SyntaxError as e:
            # AST parsing failed - this is already caught by compiler validation
            pass
        
        return violations
    
    def _detect_language_usage_inconsistency(self, text: str) -> List[Dict[str, Any]]:
       
        violations = []
        
        # Unicode script detection
        scripts = {}
        for char in text:
            if char.isalpha():
                script = self._unicode_script(char)
                scripts[script] = scripts.get(script, 0) + 1
        
        # Check for mixed scripts (excluding common mixed scenarios)
        if len(scripts) > 1:
            # Check if this is a legitimate mixed scenario
            legitimate_mixed = self._is_legitimate_mixed_language(text)
            if not legitimate_mixed:
                violations.append({
                    'type': 'mixed_language_usage',
                    'scripts': list(scripts.keys()),
                    'script_counts': scripts,
                    'text_sample': text[:100]
                })
        
        # N-gram frequency analysis for language detection
        if self.config.enable_ngram_analysis:
            ngram_issues = self._detect_ngram_language_inconsistency(text)
            violations.extend(ngram_issues)
        
        return violations

    def _unicode_script(self, char: str) -> str:
        codepoint = ord(char)
        if 0x0041 <= codepoint <= 0x024F:
            return 'Latn'
        if 0x4E00 <= codepoint <= 0x9FFF:
            return 'Hani'
        if 0x3040 <= codepoint <= 0x309F:
            return 'Hira'
        if 0x30A0 <= codepoint <= 0x30FF:
            return 'Kana'
        if 0xAC00 <= codepoint <= 0xD7AF:
            return 'Hang'
        if 0x0600 <= codepoint <= 0x06FF:
            return 'Arab'
        if 0x0400 <= codepoint <= 0x04FF:
            return 'Cyrl'
        name = unicodedata.name(char, '')
        if 'LATIN' in name:
            return 'Latn'
        if 'CJK' in name or 'IDEOGRAPH' in name:
            return 'Hani'
        return 'Other'
    
    def _detect_spelling_standard_inconsistency(self, text: str) -> List[Dict[str, Any]]:
       
        violations = []
        
        # Common US/UK spelling differences
        us_spellings = {
            'color', 'center', 'theater', 'traveled', 'counseling', 'program',
            'analyze', 'organize', 'realize', 'recognize', 'apologize'
        }
        
        uk_spellings = {
            'colour', 'centre', 'theatre', 'travelled', 'counselling', 'programme',
            'analyse', 'organise', 'realise', 'recognise', 'apologise'
        }
        
        words = re.findall(r'\b\w+\b', text.lower())
        
        us_words = [word for word in words if word in us_spellings]
        uk_words = [word for word in words if word in uk_spellings]
        
        # Check for mixed spelling standards in the same text
        if us_words and uk_words:
            violations.append({
                'type': 'spelling_standard_inconsistency',
                'us_words': us_words,
                'uk_words': uk_words,
                'mixed_standards': True
            })
        else:
            # Determine current spelling standard
            if us_words:
                current_standard = 'US'
                inconsistent_words = uk_words
            elif uk_words:
                current_standard = 'UK'
                inconsistent_words = us_words
            else:
                current_standard = None
                inconsistent_words = []
            
            # Check against session standard
            if self.session_spelling_standard is None:
                self.session_spelling_standard = current_standard
            elif current_standard and current_standard != self.session_spelling_standard:
                violations.append({
                    'type': 'spelling_standard_inconsistency',
                    'session_standard': self.session_spelling_standard,
                    'current_standard': current_standard,
                    'inconsistent_words': inconsistent_words[:5]  # Limit to first 5
                })
        
        return violations
    
    def _detect_text_structure_inconsistency(self, text: str) -> List[Dict[str, Any]]:
        
        violations = []
        
        lines = text.split('\n')
        
        # Check for inconsistent heading patterns
        heading_patterns = []
        for line in lines:
            if line.strip().startswith('#'):
                heading_patterns.append(line.strip())
        
        if len(heading_patterns) > 1:
            # Check for inconsistent heading levels
            heading_levels = [len(line) - len(line.lstrip('#')) for line in heading_patterns]
            if len(set(heading_levels)) > 3:  # Too many different heading levels
                violations.append({
                    'type': 'inconsistent_heading_structure',
                    'heading_levels': heading_levels,
                    'heading_patterns': heading_patterns[:3]  # Limit to first 3
                })
        
        # Check for inconsistent list formatting
        list_patterns = []
        for line in lines:
            if re.match(r'^\s*[-*+]\s+', line):  # Bullet lists
                list_patterns.append('bullet')
            elif re.match(r'^\s*\d+\.\s+', line):  # Numbered lists
                list_patterns.append('numbered')
        
        if list_patterns:
            bullet_count = list_patterns.count('bullet')
            numbered_count = list_patterns.count('numbered')
            
            if bullet_count > 0 and numbered_count > 0:
                violations.append({
                    'type': 'mixed_list_formatting',
                    'bullet_lists': bullet_count,
                    'numbered_lists': numbered_count
                })
        
        return violations
    
    def _is_legitimate_mixed_language(self, text: str) -> bool:
        
        translation_patterns = [
            r'\b(translation|version|original|translated)\b',
            r'\b(中文|English|日本語|한국어)\b'
        ]
        
        for pattern in translation_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Code blocks
        if re.search(r'```[\w]*\n.*\n```', text, re.DOTALL):
            return True
        
        # Structured formats
        if re.search(r':\s*[^\n]+\n.*:', text):  # Colon-separated format
            return True
        
        return False
    
    def _detect_ngram_language_inconsistency(self, text: str) -> List[Dict[str, Any]]:
        violations = []
        
        # Simple n-gram analysis for common language patterns
        words = text.lower().split()
        
        # Check for language-specific patterns
        english_patterns = ['the', 'and', 'or', 'but', 'in', 'on', 'at']
        chinese_patterns = ['的', '是', '在', '有', '和', '或']
        
        english_count = sum(1 for word in words if word in english_patterns)
        chinese_count = sum(1 for word in words if any(char in chinese_patterns for char in word))
        
        if english_count > 0 and chinese_count > 0:
            # Check if this is legitimate mixed usage
            if not self._is_legitimate_mixed_language(text):
                violations.append({
                    'type': 'ngram_language_inconsistency',
                    'english_patterns': english_count,
                    'chinese_patterns': chinese_count
                })
        
        return violations
    
    def _get_detected_languages(self, text: str) -> List[str]:
        languages = []
        
        scripts = set()
        for char in text:
            if char.isalpha():
                script = self._unicode_script(char)
                scripts.add(script)
        
        # Map scripts to languages
        script_to_lang = {
            'Latn': 'English',
            'Hani': 'Chinese',
            'Hira': 'Japanese',
            'Kana': 'Japanese',
            'Hang': 'Korean',
            'Arab': 'Arabic',
            'Cyrl': 'Russian'
        }
        
        for script in scripts:
            if script in script_to_lang:
                languages.append(script_to_lang[script])
        
        return list(set(languages)) 
