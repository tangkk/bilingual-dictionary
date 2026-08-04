#!/usr/bin/env python3
"""Build browser-friendly dictionary, POS, and example indexes."""

from __future__ import annotations

import bz2
import gzip
import json
import re
import shutil
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
OUTPUT = ROOT / "public" / "data"
TEI = "{http://www.tei-c.org/ns/1.0}"
TATOEBA_SNAPSHOT = "2026-08-01"


def compact_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def normalize_english(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9' -]+", " ", value)
    return re.sub(r"\s+", " ", value).strip(" -")


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def english_shard(term: str) -> str:
    normalized = normalize_english(term)
    safe = re.sub(r"[^a-z0-9]", "", normalized)
    return (safe + "__")[:2]


def chinese_shard(term: str) -> str:
    # Terms sharing the same first character stay together, while rare
    # characters are folded into 256 stable buckets to keep file counts low.
    return f"u{ord(term[0]) % 256:02x}" if term else "empty"


def candidate_english_terms(definition: str) -> set[str]:
    text = re.sub(r"\([^)]*\)", " ", definition)
    text = re.sub(r"\[[^]]*]", " ", text)
    text = re.sub(r"\bCL:.*$", "", text, flags=re.I)
    text = normalize_english(text)
    if not text or len(text) > 80:
        return set()
    terms = {text}
    for prefix in ("to ", "a ", "an ", "the "):
        if text.startswith(prefix) and len(text) > len(prefix) + 1:
            terms.add(text[len(prefix) :])
    for part in re.split(r"\s*(?:;|,| or | and )\s*", text):
        part = normalize_english(part)
        if 1 < len(part) <= 42 and len(part.split()) <= 5:
            terms.add(part)
    return terms


def parse_jieba_pos() -> tuple[dict[str, list[str]], dict]:
    source = VENDOR / "jieba" / "dict.txt"
    positions: dict[str, list[str]] = defaultdict(list)
    rows = 0
    with source.open("r", encoding="utf-8") as handle:
        for raw in handle:
            parts = raw.rstrip().split()
            if len(parts) < 3:
                continue
            word, tag = parts[0], parts[-1]
            if tag and tag not in positions[word]:
                positions[word].append(tag)
            rows += 1
    return positions, {"entries": rows, "license": "MIT"}


def parse_cedict(jieba_pos: dict[str, list[str]]) -> tuple[dict[str, list[dict]], dict[str, list[dict]], dict]:
    source = VENDOR / "cc-cedict" / "cedict.txt.gz"
    chinese: dict[str, list[dict]] = defaultdict(list)
    english: dict[str, list[dict]] = defaultdict(list)
    metadata: dict[str, str | int] = {}
    entry_re = re.compile(r"^(\S+)\s+(\S+)\s+\[([^]]+)]\s+/(.*)/$")

    with gzip.open(source, "rt", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line.startswith("#! ") and "=" in line:
                key, value = line[3:].split("=", 1)
                metadata[key] = int(value) if key == "entries" else value
                continue
            if not line or line.startswith("#"):
                continue
            match = entry_re.match(line)
            if not match:
                continue
            traditional, simplified, pinyin, raw_defs = match.groups()
            definitions = [clean_text(item) for item in raw_defs.split("/") if clean_text(item)]
            result = {
                "s": simplified,
                "t": traditional,
                "p": pinyin,
                "d": definitions,
                "g": jieba_pos.get(simplified, []),
                "x": "cc",
            }
            chinese[simplified].append(result)
            if traditional != simplified:
                chinese[traditional].append(result)

            compact_result = {
                "e": "",
                "z": simplified,
                "t": traditional,
                "p": pinyin,
                "g": jieba_pos.get(simplified, []),
                "x": "cc",
            }
            seen_terms: set[str] = set()
            for definition in definitions:
                for term in candidate_english_terms(definition):
                    if term in seen_terms:
                        continue
                    seen_terms.add(term)
                    item = dict(compact_result)
                    item["e"] = term
                    english[term].append(item)

    return chinese, english, metadata


def parse_freedict() -> tuple[dict[str, list[dict]], dict]:
    source = VENDOR / "freedict" / "eng-zho.tei"
    english: dict[str, list[dict]] = defaultdict(list)
    metadata: dict[str, str | int] = {"entries": 0}

    for event, element in ET.iterparse(source, events=("end",)):
        if element.tag == f"{TEI}edition":
            metadata["version"] = clean_text(element.text)
        elif element.tag == f"{TEI}date" and "date" not in metadata:
            metadata["date"] = clean_text(element.text)
        elif element.tag == f"{TEI}entry":
            headwords = [clean_text(node.text) for node in element.findall(f"./{TEI}form/{TEI}orth")]
            translations = [clean_text("".join(node.itertext())) for node in element.findall(f".//{TEI}cit[@type='trans']/{TEI}quote")]
            pronunciations = [clean_text(node.text) for node in element.findall(f"./{TEI}form/{TEI}pron")]
            parts = [clean_text(node.text) for node in element.findall(f"./{TEI}gramGrp/{TEI}pos")]
            translations = list(dict.fromkeys(item for item in translations if item))
            pronunciations = list(dict.fromkeys(item for item in pronunciations if item))
            parts = list(dict.fromkeys(item for item in parts if item))
            for headword in headwords:
                key = normalize_english(headword)
                if not key or not translations:
                    continue
                english[key].append(
                    {
                        "e": headword,
                        "z": translations,
                        "r": pronunciations,
                        "g": parts,
                        "x": "fd",
                    }
                )
                metadata["entries"] = int(metadata["entries"]) + 1
            element.clear()
    return english, metadata


def merge_english(primary: dict[str, list[dict]], secondary: dict[str, list[dict]]) -> dict[str, list[dict]]:
    merged: dict[str, list[dict]] = defaultdict(list)
    for source in (primary, secondary):
        for term, results in source.items():
            seen = {(json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in merged[term]}
            for item in results:
                signature = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if signature not in seen:
                    merged[term].append(item)
                    seen.add(signature)
    return merged


def load_selected_sentences(path: Path, wanted: set[int]) -> dict[int, tuple[str, str]]:
    selected: dict[int, tuple[str, str]] = {}
    with bz2.open(path, "rt", encoding="utf-8") as handle:
        for raw in handle:
            parts = raw.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            try:
                sentence_id = int(parts[0])
            except ValueError:
                continue
            if sentence_id in wanted:
                selected[sentence_id] = (clean_text(parts[2]), clean_text(parts[3]))
    return selected


def sentence_quality(english: str, chinese: str) -> float:
    english_words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", english)
    unusual = len(re.findall(r"[^\x00-\x7f]", english))
    return (
        abs(len(english) - 42)
        + abs(len(chinese) - 17) * 1.4
        + abs(len(english_words) - 8) * 1.8
        + unusual * 8
    )


def valid_sentence_pair(english: str, chinese: str) -> bool:
    if not (8 <= len(english) <= 110 and 4 <= len(chinese) <= 55):
        return False
    if not re.search(r"[A-Za-z]", english) or not re.search(r"[\u3400-\u9fff]", chinese):
        return False
    if english.count("http") or chinese.count("http"):
        return False
    return True


def english_ngrams(sentence: str, max_words: int = 5) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", normalize_english(sentence))
    return {
        " ".join(words[start : start + size])
        for start in range(len(words))
        for size in range(1, min(max_words, len(words) - start) + 1)
    }


def chinese_substrings(sentence: str, max_length: int = 8) -> set[str]:
    blocks = re.findall(r"[\u3400-\u9fff\uf900-\ufaff]+", sentence)
    return {
        block[start : start + size]
        for block in blocks
        for start in range(len(block))
        for size in range(2, min(max_length, len(block) - start) + 1)
    }


def build_examples(english_terms: set[str], chinese_terms: set[str]) -> tuple[dict, dict, dict]:
    tatoeba = VENDOR / "tatoeba"
    link_path = tatoeba / "cmn-eng_links.tsv.bz2"
    links: list[tuple[int, int]] = []
    chinese_ids: set[int] = set()
    english_ids: set[int] = set()
    with bz2.open(link_path, "rt", encoding="utf-8") as handle:
        for raw in handle:
            parts = raw.rstrip().split("\t")
            if len(parts) != 2:
                continue
            chinese_id, english_id = map(int, parts)
            links.append((chinese_id, english_id))
            chinese_ids.add(chinese_id)
            english_ids.add(english_id)

    chinese_sentences = load_selected_sentences(tatoeba / "cmn_sentences_detailed.tsv.bz2", chinese_ids)
    english_sentences = load_selected_sentences(tatoeba / "eng_sentences_detailed.tsv.bz2", english_ids)
    ranked_pairs: list[tuple[float, dict]] = []
    seen_text: set[tuple[str, str]] = set()
    for chinese_id, english_id in links:
        chinese_row = chinese_sentences.get(chinese_id)
        english_row = english_sentences.get(english_id)
        if not chinese_row or not english_row:
            continue
        chinese, chinese_user = chinese_row
        english, english_user = english_row
        signature = (english.casefold(), chinese)
        if signature in seen_text or not valid_sentence_pair(english, chinese):
            continue
        seen_text.add(signature)
        ranked_pairs.append(
            (
                sentence_quality(english, chinese),
                {
                    "e": english,
                    "z": chinese,
                    "ei": english_id,
                    "zi": chinese_id,
                    "eu": english_user,
                    "zu": chinese_user,
                },
            )
        )

    english_examples: dict[str, list[dict]] = defaultdict(list)
    chinese_examples: dict[str, list[dict]] = defaultdict(list)
    for _, example in sorted(ranked_pairs, key=lambda item: item[0]):
        for term in english_ngrams(example["e"]):
            if term in english_terms and len(english_examples[term]) < 3:
                english_examples[term].append(example)
        for term in chinese_substrings(example["z"]):
            if term in chinese_terms and len(chinese_examples[term]) < 3:
                chinese_examples[term].append(example)

    metadata = {
        "pairs": len(ranked_pairs),
        "englishTermsWithExamples": len(english_examples),
        "chineseTermsWithExamples": len(chinese_examples),
        "snapshot": TATOEBA_SNAPSHOT,
    }
    return english_examples, chinese_examples, metadata


def write_shards(index: dict[str, list[dict]], directory: str, shard_fn) -> tuple[int, int]:
    shards: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for term, results in index.items():
        shards[shard_fn(term)][term] = results
    for shard, payload in shards.items():
        ordered = dict(sorted(payload.items(), key=lambda item: item[0]))
        compact_json(OUTPUT / directory / f"{shard}.json", ordered)
    return len(index), len(shards)


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    jieba_pos, jieba_meta = parse_jieba_pos()
    chinese, cedict_english, cedict_meta = parse_cedict(jieba_pos)
    freedict_english, freedict_meta = parse_freedict()
    english = merge_english(freedict_english, cedict_english)

    english_examples, chinese_examples, tatoeba_meta = build_examples(set(english), set(chinese))

    zh_terms, zh_shards = write_shards(chinese, "zh", chinese_shard)
    en_terms, en_shards = write_shards(english, "en", english_shard)
    en_example_terms, en_example_shards = write_shards(english_examples, "examples/en", english_shard)
    zh_example_terms, zh_example_shards = write_shards(chinese_examples, "examples/zh", chinese_shard)

    manifest = {
        "builtAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "counts": {
            "chineseTerms": zh_terms,
            "englishTerms": en_terms,
            "chineseShards": zh_shards,
            "englishShards": en_shards,
            "englishTermsWithExamples": en_example_terms,
            "chineseTermsWithExamples": zh_example_terms,
            "exampleShards": en_example_shards + zh_example_shards,
        },
        "sources": {
            "ccCedict": {
                "entries": cedict_meta.get("entries", 0),
                "date": cedict_meta.get("date", ""),
                "license": "CC BY-SA 4.0",
                "url": "https://www.mdbg.net/chinese/dictionary?page=cc-cedict",
            },
            "freeDict": {
                "entries": freedict_meta.get("entries", 0),
                "version": freedict_meta.get("version", ""),
                "date": freedict_meta.get("date", ""),
                "license": "CC BY-SA 3.0",
                "url": "https://freedict.org/downloads/",
            },
            "jieba": {
                "entries": jieba_meta.get("entries", 0),
                "license": "MIT",
                "url": "https://github.com/fxsjy/jieba",
            },
            "tatoeba": {
                **tatoeba_meta,
                "license": "CC BY 2.0 FR",
                "url": "https://tatoeba.org/downloads",
            },
        },
    }
    compact_json(OUTPUT / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
