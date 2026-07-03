# Comfrey artifact source file.

from typing import Dict, List, Any, Optional, Tuple, Set
import logging
import re
from collections import defaultdict, deque
from difflib import SequenceMatcher

from .types import DetectionResult, RepairResult
from .config import ComfreyConfig

logger = logging.getLogger(__name__)

class RepetitionRepairer:
    
    def __init__(self, config: ComfreyConfig):
        self.config = config
        self._init_repair_components()
    
    def _init_repair_components(self):
        self.action_result_cache = {}
        
        self.cycle_detector = CycleDetector()
        
        self.content_deduplicator = ContentDeduplicator(self.config)
        
        self.relevance_filter = RelevanceFilter(self.config)
    
    def repair_software_behavior_redundancy(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        try:
            details = detection_result.details
            repair_actions = []
            
            action_signature = details.get('action_signature', '')
            redundant_actions = details.get('redundant_actions', 0)
            
            if redundant_actions > 0:
                cached_result = details.get('cached_output')
                if cached_result is None:
                    cached_result = self._get_cached_result(action_signature)
                if cached_result is not None:
                    repair_actions.append(f"Used cached result for action {action_signature}")
                    repaired_output = cached_result
                else:
                    repaired_output = output
                    self._cache_result(action_signature, output)
                    repair_actions.append(f"Executed and cached result for action {action_signature}")
            else:
                repaired_output = output
                repair_actions.append("No redundancy detected, kept original output")
            
            return RepairResult(
                success=True,
                original_output=str(output),
                repaired_output=str(repaired_output),
                repair_actions=repair_actions,
                metadata={
                    "repair_strategy": "software_behavior_redundancy",
                    "cached_actions": redundant_actions,
                    "action_signature": action_signature
                }
            )
        except Exception as e:
            logger.error(f"Software behavior redundancy repair failed: {e}")
            if self.config.strict_paper_mode or not self.config.allow_lightweight_fallbacks:
                raise
        return RepairResult(
            success=False,
            original_output=str(output),
            repaired_output=str(output),
            repair_actions=[],
            metadata={"error": str(e)}
        )
    
    def repair_semantic_redundancy(self, output: Any, detection_result: DetectionResult) -> RepairResult:
        try:
            output_str = str(output)
            details = detection_result.details
            redundancy_analysis = details.get('redundancy_analysis', {})
            bypass_reused_history = redundancy_analysis.get('external', {}).get(
                'already_repaired_by_invocation_bypass',
                False
            )
            
            repair_actions = []
            if bypass_reused_history:
                repair_actions.append("Skipped semantic repair because invocation bypass already reused history")
                return RepairResult(
                    success=True,
                    original_output=output_str,
                    repaired_output=output_str,
                    repair_actions=repair_actions,
                    metadata={
                        "repair_strategy": "semantic_redundancy_bypass",
                        "redundancy_analysis": redundancy_analysis,
                        "total_repairs": len(repair_actions)
                    }
                )
            
            cycle_terminated_output, cycle_actions = self._apply_cycle_termination(
                output_str, redundancy_analysis
            )
            repair_actions.extend(cycle_actions)
            
            content_fixed_output, content_actions = self._apply_content_fixes(
                cycle_terminated_output, redundancy_analysis
            )
            repair_actions.extend(content_actions)
            
            final_output, filter_actions = self._apply_contextual_filtering(
                content_fixed_output, redundancy_analysis
            )
            repair_actions.extend(filter_actions)
            
            return RepairResult(
                success=True,
                original_output=output_str,
                repaired_output=final_output,
                repair_actions=repair_actions,
                metadata={
                    "repair_strategy": "three_stage_semantic_redundancy",
                    "redundancy_analysis": redundancy_analysis,
                    "num_stages": 3,
                    "total_repairs": len(repair_actions)
                }
            )
        except Exception as e:
            logger.error(f"Semantic redundancy repair failed: {e}")
            if self.config.strict_paper_mode or not self.config.allow_lightweight_fallbacks:
                raise
        return RepairResult(
            success=False,
            original_output=str(output),
            repaired_output=str(output),
            repair_actions=[],
            metadata={"error": str(e)}
        )
    
    def _get_cached_result(self, action_signature: str) -> Any:
        return self.action_result_cache.get(action_signature)
    
    def _cache_result(self, action_signature: str, result: Any):
        self.action_result_cache[action_signature] = result
    
    def _apply_cycle_termination(self, output: str, redundancy_analysis: Dict) -> Tuple[str, List[str]]:
        actions = []
        
        internal_redundancy = redundancy_analysis.get('internal', {})
        if internal_redundancy.get('detected', False):
            cycle_broken_output, cycle_actions = self.cycle_detector.break_internal_cycles(output)
            actions.extend(cycle_actions)
            output = cycle_broken_output
        
        external_redundancy = redundancy_analysis.get('external', {})
        if external_redundancy.get('detected', False):
            if external_redundancy.get('already_repaired_by_invocation_bypass', False):
                actions.append("Skipped external rollback because invocation bypass already reused history")
                return output, actions
            rollback_output, rollback_actions = self.cycle_detector.rollback_to_non_redundant(
                output, external_redundancy
            )
            actions.extend(rollback_actions)
            output = rollback_output
        
        return output, actions
    
    def _apply_content_fixes(self, output: str, redundancy_analysis: Dict) -> Tuple[str, List[str]]:
        actions = []
        
        deduplicated_output, dedup_actions = self.content_deduplicator.deduplicate_sentences(output)
        actions.extend(dedup_actions)
        
        merged_output, merge_actions = self.content_deduplicator.merge_enumerations(deduplicated_output)
        actions.extend(merge_actions)
        
        diversified_output, diversify_actions = self.content_deduplicator.diversify_content(merged_output)
        actions.extend(diversify_actions)
        
        return diversified_output, actions
    
    def _apply_contextual_filtering(self, output: str, redundancy_analysis: Dict) -> Tuple[str, List[str]]:
        actions = []
        
        contextual_redundancy = redundancy_analysis.get('contextual', {})
        if contextual_redundancy.get('detected', False):
            filtered_output, filter_actions = self.relevance_filter.filter_verbose_content(
                output, contextual_redundancy
            )
            actions.extend(filter_actions)
            
            consolidated_output, consolidate_actions = self.relevance_filter.consolidate_content(
                filtered_output
            )
            actions.extend(consolidate_actions)
            
            return consolidated_output, actions
        
        return output, actions


class CycleDetector:
    
    def __init__(self):
        self.iteration_history = deque(maxlen=20)
    
    def break_internal_cycles(self, output: str) -> Tuple[str, List[str]]:
        actions = []
        
        sentences = re.split(r'[.!?]+', output)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        unique_sentences = []
        seen_sentences = set()
        
        for sentence in sentences:
            sentence_normalized = sentence.lower().strip()
            if sentence_normalized not in seen_sentences:
                unique_sentences.append(sentence)
                seen_sentences.add(sentence_normalized)
            else:
                actions.append(f"Removed duplicate sentence: '{sentence[:50]}...'")
        
        if len(unique_sentences) < len(sentences):
            repaired_output = '. '.join(unique_sentences) + '.'
            actions.append(f"Broke internal cycles: {len(sentences)} -> {len(unique_sentences)} sentences")
        else:
            repaired_output = output
        
        return repaired_output, actions
    
    def rollback_to_non_redundant(self, output: str, external_redundancy: Dict) -> Tuple[str, List[str]]:
        actions = []
        
        redundant_history = external_redundancy.get('redundant_history', [])
        
        if redundant_history:
            previous = redundant_history[-1]
            repaired_output = str(previous.get('processed_output', previous.get('original_output', output)))
            actions.append("Rolled back to previous processed output for external redundancy")
        else:
            repaired_output = output
        
        return repaired_output, actions


class ContentDeduplicator:
    
    def __init__(self, config: ComfreyConfig):
        self.config = config
    
    def deduplicate_sentences(self, output: str) -> Tuple[str, List[str]]:
        actions = []
        
        sentences = re.split(r'[.!?]+', output)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        unique_sentences = []
        for sentence in sentences:
            is_duplicate = False
            for existing in unique_sentences:
                similarity = SequenceMatcher(None, sentence.lower(), existing.lower()).ratio()
                if similarity > 0.8:  
                    is_duplicate = True
                    actions.append(f"Removed semantically similar sentence: '{sentence[:50]}...'")
                    break
            
            if not is_duplicate:
                unique_sentences.append(sentence)
        
        repaired_output = '. '.join(unique_sentences) + '.' if unique_sentences else output
        
        if len(unique_sentences) < len(sentences):
            actions.append(f"Deduplicated sentences: {len(sentences)} -> {len(unique_sentences)}")
        
        return repaired_output, actions
    
    def merge_enumerations(self, output: str) -> Tuple[str, List[str]]:
        actions = []
        
        enum_patterns = [
            r'(\d+\.)\s*([^.]+)',  
            r'([a-z]\))\s*([^.]+)',  
            r'([-*+])\s*([^.]+)',  
        ]
        
        for pattern in enum_patterns:
            matches = re.findall(pattern, output)
            if len(matches) > 1:
                seen_items = set()
                unique_items = []
                
                for marker, item in matches:
                    item_normalized = item.lower().strip()
                    if item_normalized not in seen_items:
                        unique_items.append((marker, item))
                        seen_items.add(item_normalized)
                    else:
                        actions.append(f"Merged duplicate enumeration item: '{item[:30]}...'")
                
                if len(unique_items) < len(matches):
                    new_enum = []
                    for i, (marker, item) in enumerate(unique_items):
                        if marker.isdigit():
                            new_enum.append(f"{i+1}. {item}")
                        else:
                            new_enum.append(f"{marker} {item}")
                    
                    enum_section = '\n'.join(new_enum)
                    output = re.sub(pattern, '', output)
                    output += '\n' + enum_section
                    actions.append(f"Merged enumeration: {len(matches)} -> {len(unique_items)} items")
        
        return output, actions
    
    def diversify_content(self, output: str) -> Tuple[str, List[str]]:
        actions = []
        
        words = output.split()
        word_freq = defaultdict(int)
        
        for word in words:
            if len(word) > 3:  
                word_freq[word.lower()] += 1
        
        repeated_words = {word: freq for word, freq in word_freq.items() if freq > 5}
        
        if repeated_words:
            diversified_output = output
            for word, freq in repeated_words.items():
                pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
                matches = list(pattern.finditer(diversified_output))
                
                if len(matches) > 3:
                    for i in range(3, len(matches), 2):
                        match = matches[i]
                        diversified_output = (diversified_output[:match.start()] + 
                                            diversified_output[match.end():])
                        actions.append(f"Reduced repetition of word: '{word}'")
            
            return diversified_output, actions
        
        return output, actions


class RelevanceFilter:
    
    def __init__(self, config: ComfreyConfig):
        self.config = config
    
    def filter_verbose_content(self, output: str, contextual_redundancy: Dict) -> Tuple[str, List[str]]:
        actions = []
        
        verbose_indicators = contextual_redundancy.get('verbose_indicators', [])
        
        if verbose_indicators:
            sentences = re.split(r'[.!?]+', output)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            filtered_sentences = []
            for sentence in sentences:
                is_verbose = False
                
                for indicator in verbose_indicators:
                    if 'phrase' in indicator.lower():
                        phrase_match = re.search(r"'([^']+)'", indicator)
                        if phrase_match:
                            phrase = phrase_match.group(1)
                            if phrase.lower() in sentence.lower():
                                is_verbose = True
                                actions.append(f"Filtered verbose sentence with phrase: '{phrase}'")
                                break
                
                if not is_verbose:
                    words = sentence.split()
                    if len(words) > 10:  
                        word_freq = defaultdict(int)
                        for word in words:
                            word_freq[word.lower()] += 1
                        
                        max_freq = max(word_freq.values()) if word_freq else 0
                        if max_freq > len(words) * 0.3:  
                            is_verbose = True
                            actions.append(f"Filtered verbose sentence with repetition: '{sentence[:50]}...'")
                
                if not is_verbose:
                    filtered_sentences.append(sentence)
            
            if len(filtered_sentences) < len(sentences):
                repaired_output = '. '.join(filtered_sentences) + '.' if filtered_sentences else ""
                actions.append(f"Filtered verbose content: {len(sentences)} -> {len(filtered_sentences)} sentences")
            else:
                repaired_output = output
        else:
            repaired_output = output
        
        return repaired_output, actions
    
    def consolidate_content(self, output: str) -> Tuple[str, List[str]]:
        actions = []
        
        sentences = re.split(r'[.!?]+', output)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 1:
            return output, actions
        
        sentence_groups = []
        current_group = [sentences[0]]
        
        for i in range(1, len(sentences)):
            similarity_scores = []
            for group_sentence in current_group:
                sim = SequenceMatcher(None, sentences[i].lower(), group_sentence.lower()).ratio()
                similarity_scores.append(sim)
            
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            
            if avg_similarity > 0.3:  
                current_group.append(sentences[i])
            else:
                sentence_groups.append(current_group)
                current_group = [sentences[i]]
        
        sentence_groups.append(current_group)
        
        consolidated_sentences = []
        for group in sentence_groups:
            if len(group) > 1:
                consolidated_sentence = group[0]  
                for sentence in group[1:]:
                    words_existing = set(consolidated_sentence.lower().split())
                    words_new = set(sentence.lower().split())
                    unique_words = words_new - words_existing
                    
                    if len(unique_words) > 2:  
                        consolidated_sentence += f" {sentence}"
                
                consolidated_sentences.append(consolidated_sentence)
                actions.append(f"Consolidated {len(group)} related sentences")
            else:
                consolidated_sentences.append(group[0])
        
        repaired_output = '. '.join(consolidated_sentences) + '.' if consolidated_sentences else output
        
        return repaired_output, actions 
