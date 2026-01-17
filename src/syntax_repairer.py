

import ast
import dis
import re
import logging
from typing import Dict, List, Any, Optional, Tuple

from .types import DetectionResult, RepairResult, ErrorType
from .config import ComfreyConfig

logger = logging.getLogger(__name__)

class SyntaxRepairer:
  
    
    def __init__(self, config: ComfreyConfig):
        self.config = config
        self.repair_cache = {} if config.enable_repair_caching else None
        
    def repair_parser_misalignment(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        
        try:
            output_str = str(output)
            original_output = output_str
            violations = detection_result.details.get("violations", [])
            repair_actions = []
            current_output = output_str
            
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                retry_count += 1
                
                ast_repaired_output, ast_repairs = self._ast_domain_repair(current_output, violations)
                repair_actions.extend(ast_repairs)
                
                if self._validate_bytecode_compilation(ast_repaired_output):
                    current_output = ast_repaired_output
                    repair_actions.append(f"AST refinement successful on retry {retry_count}")
                    break
                else:
                    current_output, fallback_repairs = self._fallback_syntax_repairs(current_output, violations)
                    repair_actions.extend(fallback_repairs)
                    
                    if self._validate_bytecode_compilation(current_output):
                        repair_actions.append(f"Fallback repair successful on retry {retry_count}")
                        break
                    
                    if retry_count < max_retries:
                        repair_actions.append(f"Retry {retry_count} failed, attempting retry {retry_count + 1}")
            
            success = len(repair_actions) > 0 and current_output != original_output
            
            return RepairResult(
                success=success,
                original_output=original_output,
                repaired_output=current_output,
                repair_actions=repair_actions,
                metadata={
                    "violation_count": len(violations),
                    "repair_type": "syntax_fix"
                }
            )
            
        except Exception as e:
            logger.error(f"Error in syntax repair: {str(e)}")
            return RepairResult(
                success=False,
                original_output=str(output),
                repaired_output=str(output),
                repair_actions=[],
                metadata={"error": str(e)}
            )
    
    def repair_lexical_inconsistency(self, output: Any, detection_result: DetectionResult) -> RepairResult:
     
        try:
            output_str = str(output)
            original_output = output_str
            violations = detection_result.details.get("violations", [])
            repair_actions = []
            current_output = output_str
            
            current_output, spelling_repairs = self._repair_spelling_inconsistency(current_output, violations)
            repair_actions.extend(spelling_repairs)
            
            current_output, language_repairs = self._repair_language_inconsistency(current_output, violations)
            repair_actions.extend(language_repairs)
            
            current_output, grammar_repairs = self._repair_grammatical_inconsistency(current_output, violations)
            repair_actions.extend(grammar_repairs)
            
            success = len(repair_actions) > 0 and current_output != original_output
            
            return RepairResult(
                success=success,
                original_output=original_output,
                repaired_output=current_output,
                repair_actions=repair_actions,
                metadata={
                    "violation_count": len(violations),
                    "repair_type": "lexical_standardization"
                }
            )
            
        except Exception as e:
            logger.error(f"Error in lexical repair: {str(e)}")
            return RepairResult(
                success=False,
                original_output=str(output),
                repaired_output=str(output),
                repair_actions=[],
                metadata={"error": str(e)}
            )
    
    def _ast_domain_repair(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
      
        repairs = []
        current_text = text
        
        try:
            tree = ast.parse(current_text)
            
            refined_tree, ast_repairs = self._refine_ast_with_minimal_edits(tree, violations)
            repairs.extend(ast_repairs)
            
            try:
                import astor
                current_text = astor.to_source(refined_tree)
                repairs.append("Applied AST refinement with minimal edit distance")
            except ImportError:
                current_text, manual_repairs = self._manual_ast_fixes(current_text, violations)
                repairs.extend(manual_repairs)
                
        except SyntaxError as e:
         
            current_text, targeted_repairs = self._targeted_syntax_fixes(current_text, violations)
            repairs.extend(targeted_repairs)
        
        return current_text, repairs
    
    def _refine_ast_with_minimal_edits(self, tree: ast.AST, violations: List[Dict[str, Any]]) -> Tuple[ast.AST, List[str]]:
  
        repairs = []
        
        class ASTRefiner(ast.NodeTransformer):
            def __init__(self):
                self.repairs_made = []
            
            def visit_FunctionDef(self, node):
                if not node.body:
                    node.body = [ast.Pass()]
                    self.repairs_made.append(f"Added pass statement to empty function '{node.name}'")
                
                has_return = any(isinstance(child, ast.Return) for child in ast.walk(node))
                if not has_return and node.name != '__init__':
                    return_stmt = ast.Return(value=ast.Constant(value=None))
                    node.body.append(return_stmt)
                    self.repairs_made.append(f"Added return statement to function '{node.name}'")
                
                return self.generic_visit(node)
            
            def visit_Call(self, node):
                if hasattr(node.func, 'id') and node.func.id and not node.args and not node.keywords:
                    pass
                
                return self.generic_visit(node)
        
        refiner = ASTRefiner()
        refined_tree = refiner.visit(tree)
        repairs.extend(refiner.repairs_made)
        
        return refined_tree, repairs
    
    def _manual_ast_fixes(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
       
        repairs = []
        current_text = text
        
        if re.search(r'def\s+\w+\([^)]*\)\s*$', current_text, re.MULTILINE):
            current_text = re.sub(r'(def\s+\w+\([^)]*\))\s*$', r'\1:', current_text, flags=re.MULTILINE)
            repairs.append("Added missing colons after function definitions")
        
        if re.search(r'def\s+\w+\([^)]*\):\s*$', current_text, re.MULTILINE):
            current_text = re.sub(r'(def\s+\w+\([^)]*\):)\s*$', r'\1\n    pass', current_text, flags=re.MULTILINE)
            repairs.append("Added pass statements to empty function bodies")
        
        return current_text, repairs
    
    def _targeted_syntax_fixes(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
      
        repairs = []
        current_text = text
        
        current_text, bracket_repairs = self._fix_bracket_mismatches(current_text)
        repairs.extend(bracket_repairs)
        
        current_text, comma_repairs = self._fix_trailing_commas(current_text)
        repairs.extend(comma_repairs)
        
        current_text, operator_repairs = self._fix_invalid_operators(current_text)
        repairs.extend(operator_repairs)
        
        current_text, expression_repairs = self._fix_incomplete_expressions(current_text)
        repairs.extend(expression_repairs)
        
        return current_text, repairs
    
    def _fallback_syntax_repairs(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    
        repairs = []
        current_text = text
        
        current_text, basic_repairs = self._repair_basic_syntax_errors(current_text, violations)
        repairs.extend(basic_repairs)
        
        current_text, bracket_repairs = self._repair_bracket_mismatches(current_text, violations)
        repairs.extend(bracket_repairs)
        
        return current_text, repairs
    
    def _fix_bracket_mismatches(self, text: str) -> Tuple[str, List[str]]:

        repairs = []
        current_text = text
        
        open_parens = current_text.count('(')
        close_parens = current_text.count(')')
        if open_parens > close_parens:
            current_text += ')' * (open_parens - close_parens)
            repairs.append(f"Added {open_parens - close_parens} missing closing parentheses")
        elif close_parens > open_parens:
            current_text = '(' * (close_parens - open_parens) + current_text
            repairs.append(f"Added {close_parens - open_parens} missing opening parentheses")
        
        single_quotes = current_text.count("'")
        if single_quotes % 2 == 1:
            current_text += "'"
            repairs.append("Added missing closing single quote")
        
        double_quotes = current_text.count('"')
        if double_quotes % 2 == 1:
            current_text += '"'
            repairs.append("Added missing closing double quote")
        
        return current_text, repairs
    
    def _fix_trailing_commas(self, text: str) -> Tuple[str, List[str]]:

        repairs = []
        current_text = text
        
        patterns = [
            (r',(\s*\))', r'\1'), 
            (r',(\s*\])', r'\1'),  
            (r',(\s*\})', r'\1'),  
        ]
        
        for pattern, replacement in patterns:
            if re.search(pattern, current_text):
                current_text = re.sub(pattern, replacement, current_text)
                repairs.append(f"Fixed trailing comma: {pattern}")
        
        return current_text, repairs
    
    def _fix_invalid_operators(self, text: str) -> Tuple[str, List[str]]:

        repairs = []
        current_text = text
        
        operator_fixes = [
            (r'=\s*=\s*=', '=='),  
            (r'!\s*=\s*=', '!='),  
            (r'<\s*=\s*>', '!='),  
        ]
        
        for pattern, replacement in operator_fixes:
            if re.search(pattern, current_text):
                current_text = re.sub(pattern, replacement, current_text)
                repairs.append(f"Fixed invalid operator: {pattern} -> {replacement}")
        
        return current_text, repairs
    
    def _fix_incomplete_expressions(self, text: str) -> Tuple[str, List[str]]:

        repairs = []
        current_text = text
        
        if re.search(r'\w+\s*=\s*$', current_text, re.MULTILINE):
            current_text = re.sub(r'(\w+\s*=)\s*$', r'\1 None', current_text, flags=re.MULTILINE)
            repairs.append("Completed incomplete assignment with None")
        
        if re.search(r'\w+\(\s*$', current_text, re.MULTILINE):
            current_text = re.sub(r'(\w+\()\s*$', r'\1)', current_text, flags=re.MULTILINE)
            repairs.append("Completed incomplete function call")
        
        return current_text, repairs

    def _repair_basic_syntax_errors(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
   
        repairs = []
        current_text = text
        
        if 'def ' in current_text and '(' in current_text and ')' not in current_text:
            lines = current_text.split('\n')
            for i, line in enumerate(lines):
                if 'def ' in line and '(' in line and ')' not in line:
                    lines[i] = line + ')'
                    repairs.append(f"Added missing closing parenthesis in function definition")
                    break
            current_text = '\n'.join(lines)
        
        if "'" in current_text and current_text.count("'") % 2 == 1:
            last_quote_pos = current_text.rfind("'")
            if last_quote_pos != -1:
                current_text = current_text[:last_quote_pos + 1] + "'" + current_text[last_quote_pos + 1:]
                repairs.append("Added missing closing quote")
        
        if 'def ' in current_text and '(' in current_text and ':' not in current_text:
            lines = current_text.split('\n')
            for i, line in enumerate(lines):
                if 'def ' in line and '(' in line and ')' in line and ':' not in line:
                    lines[i] = line + ':'
                    repairs.append("Added missing colon after function definition")
                    break
            current_text = '\n'.join(lines)
        
        return current_text, repairs
    
    def _repair_bracket_mismatches(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:

        repairs = []
        current_text = text
        
        bracket_violations = [v for v in violations if v.get("type", "").endswith("bracket")]
        
        for violation in bracket_violations:
            violation_type = violation.get("type")
            
            if violation_type == "unmatched_opening_bracket":
                position = violation.get("position", 0)
                bracket = violation.get("bracket", "")
                closing_bracket = self._get_closing_bracket(bracket)
                
                if closing_bracket:
                    insertion_point = self._find_bracket_insertion_point(current_text, position)
                    current_text = current_text[:insertion_point] + closing_bracket + current_text[insertion_point:]
                    repairs.append(f"Inserted missing '{closing_bracket}' at position {insertion_point}")
            
            elif violation_type == "unmatched_closing_bracket":
                position = violation.get("position", 0)
                bracket = violation.get("bracket", "")
                opening_bracket = self._get_opening_bracket(bracket)
                
                if opening_bracket:
                    insertion_point = self._find_opening_bracket_insertion_point(current_text, position)
                    current_text = current_text[:insertion_point] + opening_bracket + current_text[insertion_point:]
                    repairs.append(f"Inserted missing '{opening_bracket}' at position {insertion_point}")
            
            elif violation_type == "mismatched_bracket":
                position = violation.get("position", 0)
                expected = violation.get("expected", "")
                found = violation.get("found", "")
                
                if position < len(current_text) and current_text[position] == found:
                    current_text = current_text[:position] + expected + current_text[position + 1:]
                    repairs.append(f"Replaced '{found}' with '{expected}' at position {position}")
        
        return current_text, repairs
    
    def _repair_invalid_operators(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    
        repairs = []
        current_text = text
        
        operator_violations = [v for v in violations if v.get("type") == "invalid_operator"]
        
        operator_violations.sort(key=lambda x: x.get("position", 0), reverse=True)
        
        for violation in operator_violations:
            position = violation.get("position", 0)
            operator = violation.get("operator", "")
            suggestion = violation.get("suggestion", "")
            
            if position < len(current_text) and suggestion:
                if current_text[position:position + len(operator)] == operator:
                    current_text = (current_text[:position] + suggestion + 
                                  current_text[position + len(operator):])
                    repairs.append(f"Replaced '{operator}' with '{suggestion}' at position {position}")
        
        return current_text, repairs
    
    def _repair_ast_violations(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
 
        repairs = []
        current_text = text
        
        try:
            tree = ast.parse(current_text)
            
            class ASTTransformer(ast.NodeTransformer):
                def __init__(self):
                    self.repairs_made = []
                
                def visit_FunctionDef(self, node):
                    has_return = any(isinstance(child, ast.Return) for child in ast.walk(node))
                    if not has_return and node.name != '__init__':
                        return_stmt = ast.Return(value=ast.Constant(value=None))
                        node.body.append(return_stmt)
                        self.repairs_made.append(f"Added return statement to function '{node.name}'")
                    
                    return self.generic_visit(node)
                
                def visit_Name(self, node):
                    if isinstance(node.ctx, ast.Load) and node.id.startswith('undefined_'):
                        node.id = 'None'
                        self.repairs_made.append(f"Replaced undefined variable with 'None'")
                    
                    return node
            
            transformer = ASTTransformer()
            new_tree = transformer.visit(tree)
            
            if transformer.repairs_made:
                import astor  
                try:
                    current_text = astor.to_source(new_tree)
                    repairs.extend(transformer.repairs_made)
                except ImportError:
                    repairs.append("AST transformations applied (astor not available for source generation)")
            
        except SyntaxError:
            pass
        except Exception as e:
            logger.debug(f"AST repair failed: {str(e)}")
        
        return current_text, repairs
    
    def _repair_spelling_inconsistency(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
      
        repairs = []
        current_text = text
        
        spelling_violations = [v for v in violations if v.get("type") == "spelling_standard_inconsistency"]
        
        for violation in spelling_violations:
            if violation.get("mixed_standards", False):
                us_words = violation.get("us_words", [])
                uk_words = violation.get("uk_words", [])
                
                uk_to_us_patterns = [
                    (r'\bcolour\b', 'color'),
                    (r'\bcentre\b', 'center'),
                    (r'\btheatre\b', 'theater'),
                    (r'\btravelled\b', 'traveled'),
                    (r'\bcounselling\b', 'counseling'),
                    (r'\bprogramme\b', 'program'),
                    (r'\banalyse\b', 'analyze'),
                    (r'\borganise\b', 'organize'),
                    (r'\brealise\b', 'realize'),
                    (r'\brecognise\b', 'recognize'),
                    (r'\bapologise\b', 'apologize'),
                ]
                
                for uk_pattern, us_replacement in uk_to_us_patterns:
                    if re.search(uk_pattern, current_text, re.IGNORECASE):
                        current_text = re.sub(uk_pattern, us_replacement, current_text, flags=re.IGNORECASE)
                        repairs.append(f"Standardized spelling: {uk_pattern} -> {us_replacement}")
            else:
                us_count = violation.get("us_count", 0)
                uk_count = violation.get("uk_count", 0)
                
                if us_count > uk_count:
                    target_standard = "US"
                    uk_to_us_patterns = [
                        (r'\b(\w*)ise\b', r'\1ize'),
                        (r'\b(\w*)isation\b', r'\1ization'),
                        (r'\bcolour\b', 'color'),
                        (r'\bhonour\b', 'honor'),
                        (r'\bcentre\b', 'center'),
                        (r'\btheatre\b', 'theater'),
                    ]
                    
                    for uk_pattern, us_replacement in uk_to_us_patterns:
                        if re.search(uk_pattern, current_text):
                            current_text = re.sub(uk_pattern, us_replacement, current_text)
                            repairs.append(f"Converted UK spelling to US: {uk_pattern} -> {us_replacement}")
                
                elif uk_count > us_count:
                    target_standard = "UK"
                    us_to_uk_patterns = [
                        (r'\b(\w*)ize\b', r'\1ise'),
                        (r'\b(\w*)ization\b', r'\1isation'),
                        (r'\bcolor\b', 'colour'),
                        (r'\bhonor\b', 'honour'),
                        (r'\bcenter\b', 'centre'),
                        (r'\btheater\b', 'theatre'),
                    ]
                    
                    for us_pattern, uk_replacement in us_to_uk_patterns:
                        if re.search(us_pattern, current_text):
                            current_text = re.sub(us_pattern, uk_replacement, current_text)
                            repairs.append(f"Converted US spelling to UK: {us_pattern} -> {uk_replacement}")
        
        return current_text, repairs
    
    def _repair_language_inconsistency(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
       
        repairs = []
        current_text = text
        
        language_violations = [v for v in violations if v.get("type") == "mixed_languages"]
        
        for violation in language_violations:
            scripts = violation.get("scripts", [])
            
            if 'LATIN' in scripts:
                lines = current_text.split('\n')
                cleaned_lines = []
                
                for line in lines:
                    if (line.strip().startswith('```') or 
                        ':' in line or 
                        line.strip().startswith('-') or
                        line.strip().startswith('*')):
                        cleaned_lines.append(line)
                    else:
                        cleaned_line = re.sub(r'[^\x00-\x7F\s]', '', line)
                        if cleaned_line.strip():
                            cleaned_lines.append(cleaned_line)
                
                if len(cleaned_lines) < len(lines):
                    current_text = '\n'.join(cleaned_lines)
                    repairs.append("Removed mixed-language content")
        
        return current_text, repairs
    
    def _repair_grammatical_inconsistency(self, text: str, violations: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
     
        repairs = []
        current_text = text
        
        grammar_violations = [v for v in violations if v.get("type") == "inconsistent_verb_tense"]
        
        for violation in grammar_violations:
            tenses = violation.get("tenses", [])
            
            if tenses:
                most_common_tense = max(set(tenses), key=tenses.count)
                
                if most_common_tense == 'present':
                    current_text = re.sub(r'\b(\w+)ed\b', r'\1', current_text)
                    repairs.append("Converted past tense verbs to present tense")
                elif most_common_tense == 'past':
                    current_text = re.sub(r'\bis\b', 'was', current_text)
                    current_text = re.sub(r'\bare\b', 'were', current_text)
                    repairs.append("Converted present tense verbs to past tense")
        
        return current_text, repairs
    
    def _validate_bytecode_compilation(self, text: str) -> bool:
        
        try:
            compile(text, '<string>', 'exec')
            return True
        except SyntaxError:
            return False
        except Exception:
            return True
    
    def _detect_remaining_violations(self, text: str) -> List[Dict[str, Any]]:

        violations = []
        
        bracket_pairs = {'(': ')', '[': ']', '{': '}'}
        stack = []
        
        for i, char in enumerate(text):
            if char in bracket_pairs:
                stack.append(char)
            elif char in bracket_pairs.values():
                if not stack:
                    violations.append({"type": "unmatched_closing_bracket", "position": i})
                else:
                    stack.pop()
        
        while stack:
            violations.append({"type": "unmatched_opening_bracket"})
        
        return violations
    
    def _get_closing_bracket(self, opening_bracket: str) -> str:
        bracket_map = {'(': ')', '[': ']', '{': '}'}
        return bracket_map.get(opening_bracket, '')
    
    def _get_opening_bracket(self, closing_bracket: str) -> str:
        bracket_map = {')': '(', ']': '[', '}': '{'}
        return bracket_map.get(closing_bracket, '')
    
    def _find_bracket_insertion_point(self, text: str, start_pos: int) -> int:
     
        lines = text.split('\n')
        current_line = 0
        char_count = 0
        
        for i, line in enumerate(lines):
            if char_count + len(line) >= start_pos:
                current_line = i
                break
            char_count += len(line) + 1  
        
        if current_line < len(lines):
            return char_count + len(lines[current_line])
        return len(text)
    
    def _find_opening_bracket_insertion_point(self, text: str, end_pos: int) -> int:
    
        for i in range(end_pos - 1, -1, -1):
            if text[i] in ' \t\n=+\-*/(':
                return i + 1
        return 0 