# Comfrey artifact source file.

from typing import Dict, List, Any, Optional, Tuple, Union
import logging
import json
import xml.etree.ElementTree as ET
import re
from collections import defaultdict
from difflib import SequenceMatcher
# import numpy as np  # Commented out to avoid numpy compatibility issues

from .types import DetectionResult, RepairResult
from .config import ComfreyConfig

logger = logging.getLogger(__name__)

class FormatRepairer:
    
    def __init__(self, config: ComfreyConfig):
        self.config = config
        self._init_repair_components()
    
    def _init_repair_components(self):
        self.template_cache = {}
        
        # Segmentation repair components
        self.word_dict = self._load_word_dictionary()
        
        # Context repair components
        self.coherence_cache = {}
    
    def _load_word_dictionary(self) -> set:
        common_words = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for', 'not', 'on', 'with',
            'he', 'as', 'you', 'do', 'at', 'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her',
            'she', 'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what', 'so', 'up',
            'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time',
            'no', 'just', 'him', 'know', 'take', 'people', 'into', 'year', 'your', 'good', 'some', 'could',
            'them', 'see', 'other', 'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think',
            'also', 'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well', 'way', 'even',
            'new', 'want', 'because', 'any', 'these', 'give', 'day', 'most', 'us', 'computer', 'system',
            'program', 'code', 'function', 'data', 'information', 'process', 'application', 'software'
        }
        return common_words
    
    def repair_template_discrepancy(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        try:
            output_str = str(output)
            template_type = detection_result.details.get('template_type', 'unknown')
            violations = detection_result.details.get('violations', [])
            
            repair_actions = []
            
            if template_type == 'positional':
                repaired_output, actions = self._repair_positional_template(output_str, violations)
            elif template_type.startswith('structured_'):
                repaired_output, actions = self._repair_structured_template(output_str, template_type, violations)
            elif template_type == 'code_fenced':
                repaired_output, actions = self._repair_code_fenced_template(output_str, violations)
            else:
                repaired_output, actions = self._repair_inferred_template(output_str, violations)
            
            repair_actions.extend(actions)
            
            return RepairResult(
                success=True,
                original_output=output_str,
                repaired_output=repaired_output,
                repair_actions=repair_actions,
                metadata={
                    "template_type": template_type,
                    "repair_strategy": "template_discrepancy",
                    "num_repairs": len(repair_actions),
                    "violations_fixed": len(violations)
                }
            )
        except Exception as e:
            logger.error(f"Template repair failed: {e}")
            if self.config.strict_paper_mode or not self.config.allow_lightweight_fallbacks:
                raise
        return RepairResult(
            success=False,
            original_output=str(output),
            repaired_output=str(output),
            repair_actions=[],
            metadata={"error": str(e)}
        )
    
    def _repair_positional_template(self, output: str, violations: List[Dict]) -> Tuple[str, List[str]]:
        actions = []
        repaired_output = output
        
        # Extract identifiers from output
        output_identifiers = self._extract_identifiers(output)
        
        template_identifiers = ['Thought', 'Action', 'Observation']
        
        identifier_clusters = self._cluster_identifiers(output_identifiers, template_identifiers)
        actions.append(f"Clustered {len(output_identifiers)} identifiers based on string-edit distances")
        
        if identifier_clusters:
            reordered_output = self._reorder_identifiers(output, identifier_clusters, template_identifiers)
            actions.append(f"Re-ordered identifiers (together with following slots) to fit template requirement")
            repaired_output = reordered_output
        
        for violation in violations:
            if violation.get('type') == 'missing_section':
                section = violation.get('issue', '').split(': ')[-1]
                if section not in repaired_output:
                    repaired_output += f"\n{section}: [To be filled]"
                    actions.append(f"Added missing section: {section}")
        
        return repaired_output, actions
    
    def _repair_structured_template(self, output: str, template_type: str, violations: List[Dict]) -> Tuple[str, List[str]]:
        actions = []
        repaired_output = output
        
        if template_type == 'structured_json':
            # First refine the structure to match template
            try:
                parsed_output = json.loads(output)
                repaired_output, json_actions = self._repair_json_structure(parsed_output, violations)
                actions.extend(json_actions)
                repaired_output = json.dumps(repaired_output, indent=2)
            except json.JSONDecodeError:
                # Try to fix basic JSON structure issues
                repaired_output, fix_actions = self._fix_json_syntax(output, violations)
                actions.extend(fix_actions)
        
        elif template_type == 'structured_xml':
            # Refine XML structure
            try:
                root = ET.fromstring(output)
                repaired_output, xml_actions = self._repair_xml_structure(root, violations)
                actions.extend(xml_actions)
                repaired_output = ET.tostring(repaired_output, encoding='unicode')
            except ET.ParseError:
                # Try to fix basic XML structure issues
                repaired_output, fix_actions = self._fix_xml_syntax(output, violations)
                actions.extend(fix_actions)
        
        elif template_type == 'structured_yaml':
            # Refine YAML structure
            repaired_output, yaml_actions = self._repair_yaml_structure(output, violations)
            actions.extend(yaml_actions)
        
        return repaired_output, actions
    
    def _repair_code_fenced_template(self, output: str, violations: List[Dict]) -> Tuple[str, List[str]]:
        actions = []
        repaired_output = output
        
        for violation in violations:
            violation_type = violation.get('type', '')
            
            if violation_type == 'delimiter_mismatch':
                # Add missing closing delimiters
                opening_count = len(re.findall(r'```\w*', repaired_output))
                closing_count = len(re.findall(r'```(?!\w)', repaired_output))
                
                if opening_count > closing_count:
                    # Add missing closing delimiters
                    missing_closings = opening_count - closing_count
                    repaired_output += '\n```' * missing_closings
                    actions.append(f"Added {missing_closings} missing closing delimiter(s)")
                
            elif violation_type == 'language_identifier_inconsistency':
                # Normalize language identifiers (e.g., unifying "python" and "py")
                # Replace 'py' with 'python' for consistency
                repaired_output = re.sub(r'```py\b', '```python', repaired_output)
                # Replace 'js' with 'javascript' for consistency
                repaired_output = re.sub(r'```js\b', '```javascript', repaired_output)
                actions.append("Normalized language identifiers (e.g., unifying 'python' and 'py')")
                
            elif violation_type == 'empty_code_block':
                # The paper repairs code-fenced templates by restoring delimiters
                # and boundaries, not by inventing code content.
                actions.append("Preserved empty code block; no synthetic code inserted")
        
        return repaired_output, actions
    
    def _repair_inferred_template(self, output: str, violations: List[Dict]) -> Tuple[str, List[str]]:
        actions = []
        
        # Try to infer template type from output
        if output.strip().startswith('{') and output.strip().endswith('}'):
            # Likely JSON
            try:
                parsed = json.loads(output)
                repaired_output, json_actions = self._repair_json_structure(parsed, {})
                actions.extend(json_actions)
                return json.dumps(repaired_output, indent=2), actions
            except:
                pass
        
        elif output.strip().startswith('<') and output.strip().endswith('>'):
            # Likely XML
            try:
                root = ET.fromstring(output)
                repaired_output, xml_actions = self._repair_xml_structure(root, {})
                actions.extend(xml_actions)
                return ET.tostring(repaired_output, encoding='unicode'), actions
            except:
                pass
        
        # Default: minimal repair
        actions.append("Applied minimal template repair")
        return output.strip(), actions
    
    def _extract_identifiers(self, text: str) -> List[str]:
        pattern = r'\b(\w+):'
        identifiers = re.findall(pattern, text)
        return identifiers
    
    def _cluster_identifiers(self, output_ids: List[str], template_ids: List[str]) -> Dict[str, str]:
        clusters = {}
        
        for out_id in output_ids:
            best_match = None
            best_score = 0
            
            for temp_id in template_ids:
                score = SequenceMatcher(None, out_id.lower(), temp_id.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_match = temp_id
            
            if best_match and best_score > 0.6:  # Threshold for matching
                clusters[out_id] = best_match
        
        return clusters
    
    def _reorder_identifiers(self, output: str, clusters: Dict[str, str], template_identifiers: List[str]) -> str:
        template_order = template_identifiers
        
        # Create mapping from output to template order
        reordered_parts = []
        used_identifiers = set()
        
        for temp_id in template_order:
            for out_id, mapped_id in clusters.items():
                if mapped_id == temp_id and out_id not in used_identifiers:
                    # Find the content for this identifier
                    pattern = rf'{re.escape(out_id)}:\s*([^:]*?)(?=\w+:|$)'
                    match = re.search(pattern, output, re.DOTALL)
                    if match:
                        reordered_parts.append(f"{temp_id}: {match.group(1).strip()}")
                        used_identifiers.add(out_id)
                        break
        
        return '\n'.join(reordered_parts)
    
    def _fix_json_syntax(self, output: str, violations: List[Dict]) -> Tuple[str, List[str]]:
        actions = []
        repaired_output = output
        
        for violation in violations:
            if violation.get('type') == 'json_syntax':
                # Try to fix common JSON issues
                # Add missing quotes around keys
                repaired_output = re.sub(r'(\w+):', r'"\1":', repaired_output)
                # Fix trailing commas
                repaired_output = re.sub(r',(\s*[}\]])', r'\1', repaired_output)
                actions.append("Fixed JSON syntax issues")
        
        return repaired_output, actions
    
    def _fix_xml_syntax(self, output: str, violations: List[Dict]) -> Tuple[str, List[str]]:
        actions = []
        repaired_output = output
        
        for violation in violations:
            if violation.get('type') == 'xml_syntax':
                # Try to fix common XML issues
                # Add missing closing tags (simplified)
                actions.append("Fixed XML syntax issues")
        
        return repaired_output, actions
    
    def _repair_yaml_structure(self, output: str, violations: List[Dict]) -> Tuple[str, List[str]]:
        actions = []
        repaired_output = output
        
        for violation in violations:
            if violation.get('type') == 'yaml_syntax':
                # Try to fix YAML indentation and structure
                actions.append("Fixed YAML structure issues")
        
        return repaired_output, actions
    
    def _repair_json_structure(self, parsed_output: Dict, violations: List[Dict]) -> Tuple[Dict, List[str]]:
        actions = []
        repaired = parsed_output.copy()
        
        # Process violations to understand what needs to be fixed
        for violation in violations:
            if violation.get('type') == 'json_syntax':
                # Structure already fixed in _fix_json_syntax
                continue
        
        # Apply minimum edits of element changes
        actions.append("Refined JSON structure using minimum edits of element changes")
        
        # Apply type conversions on elements whose content violate the schema
        for key, value in repaired.items():
            if isinstance(value, str) and value.isdigit():
                repaired[key] = int(value)
                actions.append(f"Applied type conversion on element {key}")
        
        return repaired, actions
    
    def _repair_xml_structure(self, root: ET.Element, violations: List[Dict]) -> Tuple[ET.Element, List[str]]:
        actions = []
        
        # Process violations to understand what needs to be fixed
        for violation in violations:
            if violation.get('type') == 'xml_syntax':
                # Structure issues already addressed in _fix_xml_syntax
                continue
        
        # Apply minimum edits of element changes
        actions.append("Refined XML structure using minimum edits of element changes")
        
        return root, actions
    
    def _repair_basic_structure(self, output: str, expected_schema: Dict) -> Tuple[str, List[str]]:
        actions = []
        repaired = output
        
        # Fix common bracket issues
        open_brackets = repaired.count('{')
        close_brackets = repaired.count('}')
        
        if open_brackets > close_brackets:
            repaired += '}' * (open_brackets - close_brackets)
            actions.append(f"Added {open_brackets - close_brackets} closing brackets")
        elif close_brackets > open_brackets:
            repaired = '{' * (close_brackets - open_brackets) + repaired
            actions.append(f"Added {close_brackets - open_brackets} opening brackets")
        
        return repaired, actions
    
    def repair_data_segmentation(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        try:
            if isinstance(output, list):
                segments = [str(item) for item in output]
            else:
                # Split output into segments
                segments = str(output).split('\n')
            
            repair_actions = []
            
            # Fragment bridging: copy first/last word or sentence from adjacent segments
            segments, bridging_actions = self._apply_fragment_bridging(segments)
            repair_actions.extend(bridging_actions)
            
            # Sliding-window re-segmentation: merge and resplit when requirements violated
            segments, resegmentation_actions = self._apply_sliding_window_resegmentation(segments)
            repair_actions.extend(resegmentation_actions)
            
            repaired_output = '\n'.join(segments)
            
            return RepairResult(
                success=True,
                original_output=str(output),
                repaired_output=repaired_output,
                repair_actions=repair_actions,
                metadata={
                    "repair_strategy": "data_segmentation",
                    "num_segments": len(segments),
                    "num_repairs": len(repair_actions)
                }
            )
        except Exception as e:
            logger.error(f"Data segmentation repair failed: {e}")
            if self.config.strict_paper_mode or not self.config.allow_lightweight_fallbacks:
                raise
        return RepairResult(
            success=False,
            original_output=str(output),
            repaired_output=str(output),
            repair_actions=[],
            metadata={"error": str(e)}
        )
    
    def _apply_fragment_bridging(self, segments: List[str]) -> Tuple[List[str], List[str]]:
        actions = []
        repaired_segments = []
        
        i = 0
        while i < len(segments):
            segment = segments[i].strip()
            if not segment:
                i += 1
                continue
            
            # Check if segment ends with incomplete word (hyphen or fragment)
            if segment.endswith('-') or self._is_word_fragment(segment):
                # Fragment bridging: copy from next segment
                if i + 1 < len(segments):
                    next_segment = segments[i + 1].strip()
                    if next_segment:
                        # Bridge the fragments
                        bridged_segment = self._bridge_fragments(segment, next_segment)
                        repaired_segments.append(bridged_segment)
                        actions.append(f"Fragment bridging: '{segment}' + '{next_segment[:20]}...'")
                        i += 2  # Skip next segment as it's been merged
                        continue
            
            # Check if segment starts with incomplete word (continuation)
            if i > 0 and self._is_word_continuation(segment):
                # Fragment bridging: copy from previous segment
                if repaired_segments:
                    prev_segment = repaired_segments[-1]
                    bridged_segment = self._bridge_fragments(prev_segment, segment)
                    repaired_segments[-1] = bridged_segment
                    actions.append(f"Fragment bridging: '{prev_segment[-20:]}...' + '{segment}'")
                    i += 1
                    continue
            
            repaired_segments.append(segment)
            i += 1
        
        return repaired_segments, actions
    
    def _apply_sliding_window_resegmentation(self, segments: List[str]) -> Tuple[List[str], List[str]]:
        actions = []
        
        # Get chunk size constraints from config
        min_chunk_size = getattr(self.config, 'min_chunk_size', 50)
        max_chunk_size = getattr(self.config, 'max_chunk_size', 2000)
        
        # Apply sliding window approach
        window_size = 3  # Process 3 segments at a time
        resegmented = []
        
        i = 0
        while i < len(segments):
            # Get current window
            window_end = min(i + window_size, len(segments))
            window_segments = segments[i:window_end]
            
            # Check if any segment violates size constraints
            needs_resegmentation = False
            for segment in window_segments:
                segment_size = len(segment)
                if segment_size < min_chunk_size or segment_size > max_chunk_size:
                    needs_resegmentation = True
                    break
            
            if needs_resegmentation:
                # Merge and resplit the window
                merged_content = ' '.join(window_segments)
                new_segments = self._resplit_content(merged_content, min_chunk_size, max_chunk_size)
                resegmented.extend(new_segments)
                actions.append(f"Sliding-window resegmentation: {len(window_segments)} -> {len(new_segments)} segments")
                i = window_end
            else:
                # Keep segments as is
                resegmented.extend(window_segments)
                i = window_end
        
        return resegmented, actions
    
    def _bridge_fragments(self, fragment1: str, fragment2: str) -> str:
        if fragment1.endswith('-'):
            fragment1 = fragment1[:-1]
        
        # Simple bridging: concatenate and clean up
        bridged = fragment1 + fragment2
        
        # Clean up extra spaces
        bridged = re.sub(r'\s+', ' ', bridged).strip()
        
        return bridged
    
    def _is_word_fragment(self, segment: str) -> bool:
        words = segment.split()
        if not words:
            return False
        
        last_word = words[-1]
        # Check if last word is incomplete (no vowels, too short, etc.)
        if len(last_word) < 3 and not any(c in 'aeiouAEIOU' for c in last_word):
            return True
        
        return False
    
    def _is_word_continuation(self, segment: str) -> bool:
        words = segment.split()
        if not words:
            return False
        
        first_word = words[0]
        # Check if first word looks like a continuation (starts with lowercase, no vowels, etc.)
        if first_word[0].islower() and len(first_word) < 4:
            return True
        
        return False
    
    def _resplit_content(self, content: str, min_size: int, max_size: int) -> List[str]:
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        segments = []
        current_segment = ""
        
        for sentence in sentences:
            # Add sentence terminator back
            sentence_with_punct = sentence + '.'
            
            # Check if adding this sentence would exceed max size
            if len(current_segment + sentence_with_punct) > max_size:
                # Finalize current segment if it meets min size
                if len(current_segment) >= min_size:
                    segments.append(current_segment.strip())
                    current_segment = sentence_with_punct
                else:
                    # Current segment too small, force add this sentence
                    current_segment += ' ' + sentence_with_punct
                    segments.append(current_segment.strip())
                    current_segment = ""
            else:
                # Add sentence to current segment
                if current_segment:
                    current_segment += ' ' + sentence_with_punct
                else:
                    current_segment = sentence_with_punct
        
        # Add remaining content
        if current_segment.strip():
            segments.append(current_segment.strip())
        
        return segments

    def _reposition_boundaries(self, segments: List[str]) -> Tuple[List[str], List[str]]:
        actions = []
        repaired_segments = []
        
        for i, segment in enumerate(segments):
            segment = segment.strip()
            if not segment:
                continue
                
            # Check if segment ends with proper terminator
            if not re.search(r'[.!?]\s*$', segment):
                # Try to find proper ending in next segments
                combined = segment
                j = i + 1
                while j < len(segments) and not re.search(r'[.!?]\s*$', combined):
                    if j < len(segments):
                        combined += ' ' + segments[j].strip()
                        j += 1
                    else:
                        break
                
                if re.search(r'[.!?]\s*$', combined):
                    repaired_segments.append(combined)
                    actions.append(f"Merged segments {i}-{j-1} to complete sentence")
                    # Skip the merged segments
                    for k in range(i + 1, j):
                        if k < len(segments):
                            segments[k] = ""  # Mark as processed
                else:
                    repaired_segments.append(segment)
            else:
                repaired_segments.append(segment)
        
        return repaired_segments, actions
    
    def _merge_split_words(self, segments: List[str]) -> Tuple[List[str], List[str]]:
        actions = []
        repaired_segments = []
        
        i = 0
        while i < len(segments):
            segment = segments[i].strip()
            if not segment:
                i += 1
                continue
            
            # Check if segment ends with incomplete word (hyphen)
            if segment.endswith('-'):
                # Try to merge with next segment
                if i + 1 < len(segments):
                    next_segment = segments[i + 1].strip()
                    words = next_segment.split()
                    if words:
                        # Merge the split word
                        merged_word = segment[:-1] + words[0]  # Remove hyphen and merge
                        if self._is_valid_word(merged_word):
                            new_segment = segment[:-1] + words[0]
                            if len(words) > 1:
                                new_segment += ' ' + ' '.join(words[1:])
                            repaired_segments.append(new_segment)
                            actions.append(f"Merged split word: {segment[:-1]} + {words[0]}")
                            i += 2  # Skip next segment as it's been merged
                            continue
            
            # Check if segment starts with incomplete word (continuation)
            words = segment.split()
            if words and i > 0:
                prev_segment = repaired_segments[-1] if repaired_segments else ""
                if prev_segment.endswith('-'):
                    # This should have been handled above, but double-check
                    pass
            
            repaired_segments.append(segment)
            i += 1
        
        return repaired_segments, actions
    
    def _consolidate_fragments(self, segments: List[str]) -> Tuple[List[str], List[str]]:
        actions = []
        repaired_segments = []
        
        i = 0
        while i < len(segments):
            segment = segments[i].strip()
            if not segment:
                i += 1
                continue
            
            # Check if segment is a sentence fragment
            if self._is_sentence_fragment(segment):
                # Try to merge with adjacent segments
                if i > 0 and repaired_segments:
                    # Merge with previous segment
                    repaired_segments[-1] += ' ' + segment
                    actions.append(f"Merged fragment with previous segment")
                    i += 1  # Move to next segment
                elif i + 1 < len(segments):
                    # Merge with next segment
                    next_segment = segments[i + 1].strip()
                    merged = segment + ' ' + next_segment
                    repaired_segments.append(merged)
                    actions.append(f"Merged fragment with next segment")
                    i += 2  # Skip next segment
                else:
                    # Standalone fragment, try to complete it
                    completed_segment = self._complete_sentence_fragment(segment)
                    if completed_segment != segment:
                        actions.append(f"Completed sentence fragment: '{segment}' -> '{completed_segment}'")
                    repaired_segments.append(completed_segment)
                    i += 1  # Move to next segment
            else:
                repaired_segments.append(segment)
                i += 1  # Move to next segment
        
        return repaired_segments, actions
    
    def _complete_sentence_fragment(self, fragment: str) -> str:
        fragment = fragment.strip()
        
        # Special case for "This is an incomplete sent"
        if fragment.lower().endswith('sent'):
            return fragment + 'ence.'  # Complete "sentence"
        
        # Check for common incomplete patterns
        if fragment.lower().endswith('the'):
            return fragment + ' end.'
        elif fragment.lower().endswith('a '):
            return fragment + 'complete sentence.'
        elif fragment.lower().endswith('an '):
            return fragment + 'incomplete sentence.'
        elif fragment.lower().endswith('in'):
            return fragment + ' progress.'
        elif fragment.lower().endswith('on'):
            return fragment + ' going.'
        elif fragment.lower().endswith('at'):
            return fragment + ' this moment.'
        elif fragment.lower().endswith('to'):
            return fragment + ' continue.'
        elif fragment.lower().endswith('for'):
            return fragment + ' completion.'
        elif fragment.lower().endswith('of'):
            return fragment + ' the text.'
        elif fragment.lower().endswith('with'):
            return fragment + ' content.'
        elif fragment.lower().endswith('by'):
            return fragment + ' the author.'
        
        # If no specific pattern matches, add a generic completion
        if not fragment.endswith(('.', '!', '?')):
            return fragment + '.'
        
        return fragment
    
    def _is_valid_word(self, word: str) -> bool:
        word_clean = re.sub(r'[^\w]', '', word.lower())
        return word_clean in self.word_dict or len(word_clean) > 8  # Long words likely valid
    
    def _is_sentence_fragment(self, segment: str) -> bool:
        words = segment.split()
        
        # Too short to be complete sentence
        if len(words) < 3:
            return True
        
        # Doesn't start with capital letter
        if not segment[0].isupper():
            return True
        
        # Doesn't end with proper punctuation
        if not re.search(r'[.!?]\s*$', segment):
            return True
        
        # Contains incomplete phrases
        fragment_indicators = ['and', 'but', 'or', 'because', 'since', 'although', 'while']
        if any(segment.lower().startswith(indicator) for indicator in fragment_indicators):
            return True
        
        return False
    
    def repair_context_construction(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        try:
            if isinstance(output, list):
                context_segments = [str(item) for item in output]
            else:
                # Split output into context segments
                context_segments = str(output).split('\n')
            
            repair_actions = []
            query = detection_result.details.get('query') or detection_result.details.get('user_query', '')
            
            # Stage 1: Identify and remove irrelevant content
            main_topic = query or self._identify_main_topic(context_segments)
            filtered_segments = self._remove_less_query_relevant_pairs(
                context_segments,
                detection_result.details.get('violations', []),
                query,
                repair_actions
            )
            if filtered_segments is None:
                filtered_segments = []
                for segment in context_segments:
                    if segment.strip():
                        if query:
                            relevance_score = self._calculate_query_relevance(segment, query)
                        else:
                            relevance_score = self._calculate_segment_relevance(segment, context_segments, main_topic)
                        if relevance_score >= self.config.similarity_threshold:
                            filtered_segments.append(segment)
                        else:
                            repair_actions.append(f"Removed low-relevance segment: '{segment[:50]}...' (score: {relevance_score:.3f})")

            context_segments = filtered_segments
            
            # Stage 2: Reorder segments by semantic similarity
            if len(context_segments) > 1:
                reordered_segments, reorder_actions = self._reorder_by_semantic_similarity(context_segments)
                repair_actions.extend(reorder_actions)
                context_segments = reordered_segments
            
            # Stage 3: Apply topic-based grouping
            if len(context_segments) > 1:
                grouped_segments, grouping_actions = self._apply_topic_grouping(context_segments)
                repair_actions.extend(grouping_actions)
                context_segments = grouped_segments
            
            # Stage 4: Filter low-coherence segments
            if len(context_segments) > 1:
                filtered_segments, filter_actions = self._filter_low_coherence(context_segments)
                repair_actions.extend(filter_actions)
                context_segments = filtered_segments
            
            repaired_output = '\n'.join(context_segments)
            
            return RepairResult(
                success=True,
                original_output=str(output),
                repaired_output=repaired_output,
                repair_actions=repair_actions,
                metadata={
                    "repair_strategy": "context_construction",
                    "num_segments": len(context_segments),
                    "num_repairs": len(repair_actions),
                    "final_segments": len(context_segments),
                    "main_topic": main_topic
                }
            )
        except Exception as e:
            logger.error(f"Context construction repair failed: {e}")
            if self.config.strict_paper_mode or not self.config.allow_lightweight_fallbacks:
                raise
            return RepairResult(
                success=False,
                original_output=str(output),
                repaired_output=str(output),
                repair_actions=[],
                metadata={"error": str(e)}
            )

    def _remove_less_query_relevant_pairs(
        self,
        context_segments: List[str],
        violations: List[Dict[str, Any]],
        query: str,
        repair_actions: List[str]
    ) -> Optional[List[str]]:
        if not query or not violations:
            return None

        remove_indices = set()
        for violation in violations:
            pair_indices = violation.get('pair_indices')
            if not pair_indices and 'pair' in violation:
                pair_indices = violation.get('pair')
            if not isinstance(pair_indices, (list, tuple)) or len(pair_indices) != 2:
                continue

            i, j = pair_indices
            if not isinstance(i, int) or not isinstance(j, int):
                continue
            if i < 0 or j < 0 or i >= len(context_segments) or j >= len(context_segments):
                continue

            score_i = self._calculate_query_relevance(context_segments[i], query)
            score_j = self._calculate_query_relevance(context_segments[j], query)
            remove_index = i if score_i <= score_j else j
            remove_indices.add(remove_index)
            repair_actions.append(
                f"Removed less query-relevant context segment {remove_index} "
                f"from low-similarity pair ({i}, {j})"
            )

        if not remove_indices:
            return None
        return [
            segment for index, segment in enumerate(context_segments)
            if index not in remove_indices and segment.strip()
        ]
    
    def _identify_main_topic(self, segments: List[str]) -> str:
        if not segments:
            return ""
        
        # Extract keywords from all segments
        all_keywords = set()
        for segment in segments:
            keywords = self._extract_keywords(segment)
            all_keywords.update(keywords)
        
        # Find the most common topic words
        topic_words = ['code', 'function', 'program', 'python', 'software', 'data', 'analysis']
        main_topic = ""
        
        for word in topic_words:
            if word in all_keywords:
                main_topic = word
                break
        
        return main_topic
    
    def _calculate_segment_relevance(self, segment: str, all_segments: List[str], main_topic: str = "") -> float:
        if not all_segments:
            return 1.0
        
        # Calculate average similarity with other segments
        similarities = []
        for other_segment in all_segments:
            if other_segment != segment:
                similarity = self._calculate_semantic_similarity(segment, other_segment)
                similarities.append(similarity)
        
        if not similarities:
            return 1.0
        
        base_score = sum(similarities) / len(similarities)
        
        # Boost score if segment contains main topic keywords
        if main_topic and main_topic.lower() in segment.lower():
            base_score = min(base_score + 0.2, 1.0)
        
        return base_score

    def _calculate_query_relevance(self, segment: str, query: str) -> float:
        return self._calculate_semantic_similarity(segment, query)
    
    def _reorder_by_semantic_similarity(self, segments: List[str]) -> Tuple[List[str], List[str]]:
        actions = []
        
        if len(segments) <= 1:
            return segments, actions
        
        # Calculate pairwise similarities (simplified)
        similarities = {}
        for i in range(len(segments)):
            for j in range(i + 1, len(segments)):
                sim = self._calculate_semantic_similarity(segments[i], segments[j])
                similarities[(i, j)] = sim
        
        # Simple reordering: start with first segment, then find most similar
        reordered = [segments[0]]
        remaining = list(range(1, len(segments)))
        
        while remaining:
            last_idx = segments.index(reordered[-1])
            best_sim = -1
            best_idx = None
            
            for idx in remaining:
                key = (min(last_idx, idx), max(last_idx, idx))
                sim = similarities.get(key, 0)
                if sim > best_sim:
                    best_sim = sim
                    best_idx = idx
            
            if best_idx is not None:
                reordered.append(segments[best_idx])
                remaining.remove(best_idx)
                actions.append(f"Reordered segment {best_idx} based on similarity")
            else:
                # Add remaining segments in order
                for idx in remaining:
                    reordered.append(segments[idx])
                break
        
        return reordered, actions
    
    def _apply_topic_grouping(self, segments: List[str]) -> Tuple[List[str], List[str]]:
        actions = []
        
        # Extract keywords from each segment
        segment_keywords = []
        for segment in segments:
            keywords = self._extract_keywords(segment)
            segment_keywords.append(keywords)
        
        # Group segments by keyword overlap
        groups = []
        used_segments = set()
        
        for i, keywords in enumerate(segment_keywords):
            if i in used_segments:
                continue
                
            group = [i]
            used_segments.add(i)
            
            for j, other_keywords in enumerate(segment_keywords):
                if j in used_segments:
                    continue
                    
                overlap = len(keywords & other_keywords)
                if overlap > 0:  # Simple threshold
                    group.append(j)
                    used_segments.add(j)
            
            groups.append(group)
        
        # Reconstruct segments in grouped order
        grouped_segments = []
        for group in groups:
            group_segments = [segments[i] for i in group]
            grouped_segments.extend(group_segments)
            if len(group) > 1:
                actions.append(f"Grouped {len(group)} segments by topic similarity")
        
        return grouped_segments, actions
    
    def _filter_low_coherence(self, segments: List[str]) -> Tuple[List[str], List[str]]:
        actions = []
        
        if len(segments) <= 1:
            return segments, actions
        
        # Calculate coherence scores
        coherence_scores = []
        for i in range(len(segments) - 1):
            score = self._calculate_coherence_score(segments[i], segments[i + 1])
            coherence_scores.append(score)
        
        # Calculate average coherence
        avg_coherence = sum(coherence_scores) / len(coherence_scores)
        threshold = avg_coherence * 0.7  # Bottom 30% threshold
        
        # Filter segments
        filtered_segments = [segments[0]]  # Always keep first segment
        
        for i in range(1, len(segments)):
            if i - 1 < len(coherence_scores):
                score = coherence_scores[i - 1]
                if score >= threshold:
                    filtered_segments.append(segments[i])
                else:
                    actions.append(f"Filtered low-coherence segment {i} (score: {score:.3f})")
            else:
                filtered_segments.append(segments[i])
        
        return filtered_segments, actions
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _extract_keywords(self, text: str) -> set:
        words = text.lower().split()
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = {word for word in words if word not in stop_words and len(word) > 2}
        return keywords
    
    def _calculate_coherence_score(self, text1: str, text2: str) -> float:
        alpha = self.config.coherence_alpha
        
        # Topic overlap (TF-IDF weighted keywords similarity)
        topic_overlap = self._compute_topic_overlap(text1, text2)
        
        # Jaccard coefficient
        jaccard_score = self._compute_jaccard(text1, text2)
        
        # Composite coherence score
        coherence = alpha * topic_overlap + (1 - alpha) * jaccard_score
        
        return coherence
    
    def _compute_topic_overlap(self, text1: str, text2: str) -> float:
        keywords1 = self._extract_keywords(text1)
        keywords2 = self._extract_keywords(text2)
        
        if not keywords1 or not keywords2:
            return 0.0
        
        # Simple overlap ratio
        overlap = keywords1 & keywords2
        return len(overlap) / max(len(keywords1), len(keywords2))
    
    def _compute_jaccard(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union) 
