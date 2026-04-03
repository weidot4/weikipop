# lookup.py - Optimized version
import logging
import math
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from src.config.config import config, MAX_DICT_ENTRIES
from src.dictionary.customdict import Dictionary, WRITTEN_FORM_INDEX, READING_INDEX, FREQUENCY_INDEX, ENTRY_ID_INDEX, DEFAULT_FREQ
from src.dictionary.deconjugator import Deconjugator, Form
from src.dictionary.yomitan_client import YomitanClient

KANJI_REGEX = re.compile(r'[\u4e00-\u9faf]')
JAPANESE_SEPARATORS = {
    "、", "。", "「", "」", "｛", "｝", "（", "）", "【", "】",
    "『", "』", "〈", "〉", "《", "》", "：", "・", "／",
    "…", "︙", "‥", "︰", "＋", "＝", "－", "÷", "？", "！",
    "．", "～", "―", "!", "?",
}

logger = logging.getLogger(__name__)


@dataclass
class DictionaryEntry:
    id: int
    written_form: str
    reading: str
    senses: list
    freq: int
    deconjugation_process: tuple
    priority: float = 0.0
    match_len: int = 0  # Add match_len field for Yomitan entries


@dataclass
class KanjiEntry:
    character: str
    meanings: List[str]
    readings: List[str]
    components: List[Dict[str, str]]
    examples: List[Dict[str, str]]


class Lookup(threading.Thread):
    def __init__(self, shared_state, popup_window):
        super().__init__(daemon=True, name="Lookup")
        self.shared_state = shared_state
        self.popup_window = popup_window
        self.last_hit_result = None

        self.dictionary = Dictionary()
        self.lookup_cache: OrderedDict = OrderedDict()
        self.CACHE_SIZE = 500

        if not self.dictionary.load_dictionary('dictionary.pkl'):
            raise RuntimeError("Failed to load dictionary.")
        self.deconjugator = Deconjugator(self.dictionary.deconjugator_rules)

        # Lazy initialization of Yomitan client - only when needed
        self._yomitan_client: Optional[YomitanClient] = None
        self._yomitan_enabled = getattr(config, "yomitan_enabled", False)
        self._yomitan_available = None  # None = untested, True/False = cached result

    @property
    def yomitan_client(self):
        """Lazy property - only create Yomitan client if actually needed"""
        if not self._yomitan_enabled:
            return None
        if self._yomitan_client is None:
            try:
                self._yomitan_client = YomitanClient(getattr(config, "yomitan_api_url", "http://127.0.0.1:19633"))
            except Exception:
                self._yomitan_enabled = False  # Disable permanently if creation fails
                return None
        return self._yomitan_client

    def clear_cache(self):
        self.lookup_cache = OrderedDict()

    def run(self):
        logger.debug("Lookup thread started.")
        while self.shared_state.running:
            try:
                hit_result = self.shared_state.lookup_queue.get()
                if not self.shared_state.running: 
                    break
                logger.debug("Lookup: Triggered")

                current_lookup_string = self._extract_lookup_string(hit_result)
                last_lookup_string = self._extract_lookup_string(self.last_hit_result)


                self.last_hit_result = hit_result

                # skip lookup if lookup string didnt change
                if current_lookup_string == last_lookup_string:
                    continue
                

                lookup_result = self.lookup(current_lookup_string) if current_lookup_string else None
                # Pass context to popup if supported
                try:
                    self.popup_window.set_latest_data(lookup_result, hit_result if isinstance(hit_result, dict) else None)
                except TypeError:
                    self.popup_window.set_latest_data(lookup_result)
            except:
                logger.exception("An unexpected error occurred in the lookup loop. Continuing...")
        logger.debug("Lookup thread stopped.")

    def _extract_lookup_string(self, hit_result: Any) -> Optional[str]:
        if not hit_result:
            return None
        if isinstance(hit_result, dict):
            return hit_result.get("lookup_string")
        if isinstance(hit_result, str):
            return hit_result
        return None

    def lookup(self, lookup_string: str) -> List:
        if not lookup_string:
            return []
        logger.info(f"Looking up: {lookup_string}")

        # Fast path: clean the text
        text = lookup_string.strip()
        text = text[:config.max_lookup_length]
        for i, ch in enumerate(text):
            if ch in JAPANESE_SEPARATORS:
                text = text[:i]
                break
        if not text:
            return []

        # Fast path: cache check (most important optimization)
        if text in self.lookup_cache:
            self.lookup_cache.move_to_end(text)
            return self.lookup_cache[text]

        # Choose lookup method based on availability (cache the availability check)
        results = self._fast_lookup(text)

        # Append kanji entry (cheap operation)
        if config.show_kanji and KANJI_REGEX.match(text[0]):
            kd = self.dictionary.kanji_entries.get(text[0])
            if kd:
                results.append(KanjiEntry(
                    character=kd['character'],
                    meanings=kd['meanings'],
                    readings=kd['readings'],
                    components=kd.get('components', []),
                    examples=kd.get('examples', []),
                ))

        # Cache results
        self.lookup_cache[text] = results
        if len(self.lookup_cache) > self.CACHE_SIZE:
            self.lookup_cache.popitem(last=False)
        return results

    def _fast_lookup(self, text: str) -> List:
        """
        Optimized lookup that prefers Yomitan but falls back to local.
        Caches Yomitan availability to avoid repeated connection checks.
        """
        # Check if Yomitan is usable (cached result)
        if self._yomitan_enabled:
            if self._yomitan_available is None:
                # First time - check connection (one-time cost)
                try:
                    client = self.yomitan_client
                    self._yomitan_available = client is not None and client.check_connection()
                    if not self._yomitan_available:
                        logger.debug("Yomitan not available, falling back to local dictionary")
                except Exception:
                    self._yomitan_available = False
                    self._yomitan_enabled = False
            
            if self._yomitan_available:
                # Use Yomitan (fast path with early exit on full match)
                return self._lookup_yomitan_optimized(text)
        
        # Fallback to local dictionary
        return self._do_lookup(text)

    def _lookup_yomitan_optimized(self, lookup_string: str) -> List[Any]:
        """
        Optimized Yomitan lookup with:
        - Early exit on perfect match
        - Minimal overhead
        - Match length tracking
        """
        if not self.yomitan_client:
            return []

        found_entries = []
        seen_keys = set()
        
        # Try exact match first (fastest path)
        exact_entries = self.yomitan_client.lookup(lookup_string) or []
        if exact_entries:
            for entry in exact_entries:
                key = (entry.written_form, entry.reading)
                if key not in seen_keys:
                    entry.match_len = len(lookup_string)
                    seen_keys.add(key)
                    found_entries.append(entry)
            # If we got an exact match, return immediately (no need to try shorter prefixes)
            if found_entries:
                return found_entries

        # No exact match - try decreasing lengths
        # Start from shorter length to avoid redundant work
        max_prefix_len = min(len(lookup_string) - 1, 20)  # Limit search depth
        for prefix_len in range(max_prefix_len, 0, -1):
            prefix = lookup_string[:prefix_len]
            entries = self.yomitan_client.lookup(prefix) or []
            if entries:
                for entry in entries:
                    key = (entry.written_form, entry.reading)
                    if key not in seen_keys:
                        entry.match_len = prefix_len
                        seen_keys.add(key)
                        found_entries.append(entry)
                
                # Stop after finding matches (Yomitan usually returns best matches first)
                if found_entries and (len(lookup_string) - prefix_len) > 3:
                    break

        return found_entries

    def _do_lookup(self, text: str) -> List[DictionaryEntry]:
        """
        Original local dictionary lookup - unchanged for performance
        """
        collected: Dict[int, Tuple[tuple, Form, int]] = {}
        found_primary_match = False

        for prefix_len in range(len(text), 0, -1):
            prefix = text[:prefix_len]

            forms = self.deconjugator.deconjugate(prefix)
            forms.add(Form(text=prefix))

            prefix_hits = []

            for form in forms:
                map_entries = self._get_map_entries(form.text)
                if not map_entries:
                    continue

                for map_entry in map_entries:
                    written = map_entry[WRITTEN_FORM_INDEX]
                    entry_id = map_entry[ENTRY_ID_INDEX]

                    if written is None and KANJI_REGEX.search(form.text):
                        logger.warning(f"Skipping malformed dictionary entry: kanji key '{form.text}'")
                        continue

                    if form.tags:
                        required_pos = form.tags[-1]
                        entry_senses = self.dictionary.entries.get(entry_id, [])
                        all_pos = {p for s in entry_senses for p in s['pos']}
                        if required_pos not in all_pos:
                            continue

                    if found_primary_match and not KANJI_REGEX.search(prefix):
                        if written and KANJI_REGEX.search(written):
                            continue

                    prefix_hits.append((map_entry, form))

            if prefix_hits:
                if not found_primary_match:
                    found_primary_match = True

                for map_entry, form in prefix_hits:
                    entry_id = map_entry[ENTRY_ID_INDEX]
                    if entry_id not in collected:
                        collected[entry_id] = (map_entry, form, prefix_len)

        return self._format_and_sort(list(collected.values()), text)

    def _get_map_entries(self, text: str) -> List[tuple]:
        result = self.dictionary.lookup_map.get(text, [])
        if result:
            return list(result)
        kata = self._hira_to_kata(text)
        if kata != text:
            result = self.dictionary.lookup_map.get(kata, [])
            if result:
                return list(result)
        hira = self._kata_to_hira(text)
        if hira != text:
            result = self.dictionary.lookup_map.get(hira, [])
            if result:
                return list(result)
        return []

    def _format_and_sort(
        self,
        raw: List[Tuple[tuple, Form, int]],
        original_lookup: str,
    ) -> List[DictionaryEntry]:
        merged: Dict[Tuple[str, str], dict] = {}

        for map_entry, form, match_len in raw:
            written = map_entry[WRITTEN_FORM_INDEX]
            reading = map_entry[READING_INDEX] or ''
            freq = map_entry[FREQUENCY_INDEX]
            entry_id = map_entry[ENTRY_ID_INDEX]

            entry_senses = self.dictionary.entries.get(entry_id, [])
            priority = self._calculate_priority(written, freq, form, match_len, original_lookup)

            key = (written, reading)
            if key not in merged:
                merged[key] = {
                    'id': entry_id,
                    'written_form': written,
                    'reading': reading,
                    'senses': list(entry_senses),
                    'freq': freq,
                    'deconjugation_process': form.process,
                    'priority': priority,
                    'match_len': match_len,
                }
            else:
                cur = merged[key]
                if entry_id != cur['id']:
                    cur['senses'].extend(entry_senses)
                if priority > cur['priority']:
                    cur['priority'] = priority
                    cur['id'] = entry_id
                    cur['deconjugation_process'] = form.process
                if freq < cur['freq']:
                    cur['freq'] = freq
                if match_len > cur['match_len']:
                    cur['match_len'] = match_len

        sorted_entries = sorted(
            merged.values(),
            key=lambda x: (x['match_len'], x['priority']),
            reverse=True,
        )

        results = []
        for d in sorted_entries[:MAX_DICT_ENTRIES]:
            results.append(DictionaryEntry(
                id=d['id'],
                written_form=d['written_form'],
                reading=d['reading'],
                senses=d['senses'],
                freq=d['freq'],
                deconjugation_process=d['deconjugation_process'],
                priority=d['priority'],
                match_len=d['match_len'],
            ))
        return results

    def _calculate_priority(
        self,
        written_form: str,
        freq: int,
        form: Form,
        match_len: int,
        original_lookup: str,
    ) -> float:
        priority = float(match_len)

        if freq < DEFAULT_FREQ:
            priority += 10.0 * (1.0 - math.log(freq) / math.log(DEFAULT_FREQ))

        original_is_kana = not KANJI_REGEX.search(original_lookup)
        written_is_kana = not KANJI_REGEX.search(written_form) if written_form else True

        if original_is_kana:
            if written_is_kana and not form.process:
                priority += 3.0

        priority -= len(form.process)
        return priority

    def _hira_to_kata(self, text: str) -> str:
        res = []
        for c in text:
            code = ord(c)
            res.append(chr(code + 0x60) if 0x3041 <= code <= 0x3096 else c)
        return ''.join(res)

    def _kata_to_hira(self, text: str) -> str:
        res = []
        for c in text:
            code = ord(c)
            if 0x30A1 <= code <= 0x30F6:
                res.append(chr(code - 0x60))
            elif code == 0x30FD:
                res.append('\u309D')
            elif code == 0x30FE:
                res.append('\u309E')
            else:
                res.append(c)
        return ''.join(res)
