#!/usr/bin/env python3
"""
Portable recon script — discovery + capture for the research pipeline.

Machine-agnostic: all paths via env vars. Falls back to DuckDuckGo if
Hermes web_search/web_extract are unavailable.

Usage:
    python3 scripts/recon.py \
        --topic "Actuators" \
        --parent "Robotics" \
        --output-root "$OUTPUT_ROOT" \
        --max-sources 10

Environment variables:
    OUTPUT_ROOT    Default output root (overridable by --output-root)
    OBSIDIAN_VAULT Obsidian vault root (used if OUTPUT_ROOT not set)
    OPENROUTER_API_KEY  LLM key for optional entity extraction enhancement
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def get_output_root(args):
    if args.output_root:
        return Path(args.output_root).expanduser().resolve()
    env = os.environ.get("OUTPUT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    vault = os.environ.get("OBSIDIAN_VAULT", str(Path.home() / "Obsidian" / "main-vault"))
    return Path(vault).expanduser().resolve() / "30-Intake" / "Spiders"

DOMAIN_BLOCKLIST = {
    "youtube.com", "youtu.be", "twitter.com", "x.com",
    "reddit.com", "redd.it", "facebook.com", "fb.com",
    "instagram.com", "tiktok.com", "pinterest.com", "quora.com",
}

# ---------------------------------------------------------------------------
# Web search fallback (DuckDuckGo)
# ---------------------------------------------------------------------------

def ddg_search(query: str, max_results: int = 5) -> List[Dict]:
    """DuckDuckGo HTML search fallback."""
    url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        results = []
        # Parse the simple table layout
        links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>', html, re.S)
        for url_match, title_match in links[:max_results]:
            title = re.sub(r"<[^>]+>", "", title_match).strip()
            if title and len(title) > 10:
                results.append({"url": url_match, "title": title})
        if not results:
            # Fallback regex for different DDG layouts
            links = re.findall(r'<a[^>]+rel="nofollow"[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.S)
            for url_match, title_match in links[:max_results]:
                title = re.sub(r"<[^>]+>", "", title_match).strip()
                if title and len(title) > 10:
                    results.append({"url": url_match, "title": title})
        return results
    except Exception:
        return []

def hermes_search(query: str, limit: int = 5) -> List[Dict]:
    """Try Hermes web_search, fall back to DDG."""
    try:
        from hermes_tools import web_search
        result = web_search(query, limit=limit)
        data = result.get("data", {}).get("web", [])
        if data:
            return [{"url": r.get("url", ""), "title": r.get("title", ""), "description": r.get("description", "")} for r in data]
    except Exception:
        pass
    return ddg_search(query, max_results=limit)

# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def extract_url_content(url: str, max_chars: int = 5000) -> str:
    """Try Hermes web_extract, fall back to urllib."""
    try:
        from hermes_tools import web_extract
        result = web_extract([url])
        results = result.get("results", [])
        if results and results[0].get("content"):
            return results[0]["content"][:max_chars]
    except Exception:
        pass
    # Fallback
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S|re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S|re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------

def is_blocked(url: str) -> bool:
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        return any(block in domain for block in DOMAIN_BLOCKLIST)
    except Exception:
        return False

def title_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa | wb), 1)

def dedup_sources(new_sources: List[Dict], existing_urls: set, existing_titles: List[str]) -> List[Dict]:
    deduped = []
    for s in new_sources:
        url = s.get("url", "")
        title = s.get("title", "")
        if not url or is_blocked(url):
            continue
        if url in existing_urls:
            continue
        if any(title_similarity(title, t) > 0.85 for t in existing_titles):
            continue
        if len(title) < 15:
            continue
        deduped.append(s)
    return deduped

# ---------------------------------------------------------------------------
# Entity extraction (regex heuristics from seed text)
# ---------------------------------------------------------------------------

CORP_SUFFIXES = r"(Inc|Corp|Ltd|LLC|Co|GmbH|ASA|NV|PLC|SA|KG|AG|Holdings|Group|Technologies|Semiconductor|Materials)"
ENTITY_VERBS = r"(manufactures|supplies|produces|develops|designs|owns|operates|controls|competes|partners)"

def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extract company and technology entity candidates from text."""
    companies = set()
    # Company suffix pattern
    for m in re.finditer(rf'([A-Z][a-zA-Z0-9\- ]+ {CORP_SUFFIXES})', text):
        companies.add(m.group(0).strip())
    # Verb-context pattern
    for m in re.finditer(rf'([A-Z][a-zA-Z0-9\- ]+) ({ENTITY_VERBS})', text):
        name = m.group(1).strip()
        if len(name) > 2 and len(name) < 50:
            companies.add(name)

    technologies = set()
    tech_patterns = [
        r'([A-Z0-9]{2,}-?\d+[a-zA-Z]?)\b',  # product codes like H200, 910C
        r'\b(EUV|DUV|HBM|CoWoS|GAA|RISC-V|CBDC|QKD|PQC|SMR)\b',
    ]
    for pattern in tech_patterns:
        for m in re.finditer(pattern, text):
            technologies.add(m.group(0))

    return {
        "companies": sorted(companies)[:20],
        "technologies": sorted(technologies)[:15],
    }

# ---------------------------------------------------------------------------
# Note creation
# ---------------------------------------------------------------------------

def slugify(s: str, max_len: int = 80) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower())
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s[:max_len].rstrip("-")

def make_recon_id(parent: str, topic: str) -> str:
    raw = f"{parent}-{topic}-{date.today().isoformat()}"
    return slugify(raw)

def write_source_note(folder: Path, source: Dict, recon_id: str, tags: List[str]) -> Path:
    sources_dir = folder / "Sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    title = source.get("title", "Untitled")
    url = source.get("url", "")
    filename = f"{slugify(title)}.md"
    path = sources_dir / filename

    content = f"""---
recon_id: {recon_id}
type: article
source_url: {url}
date: {date.today().isoformat()}
tags: [{', '.join(tags)}]
ingestion_status: captured
---

# {title}

**Source:** {url}
**Captured:** {date.today().isoformat()}

{source.get('content', 'Content not extracted. See source URL.')}

"""
    path.write_text(content, encoding="utf-8")
    return path

def write_entity_note(folder: Path, name: str, entity_type: str, recon_id: str, tags: List[str], sources: List[str]) -> Path:
    entities_dir = folder / "Entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{name}.md"
    path = entities_dir / filename

    if path.exists():
        return path  # Don't overwrite existing entities

    content = f"""---
recon_id: {recon_id}
type: {entity_type}
name: {name}
tags: [{', '.join(tags)}]
status: stub
chokepoint: unknown
geography:
role_in_value_chain:
sources:
{chr(10).join(f'  - "{s}"' for s in sources)}
---

# {name}

*Entity stub — needs deepening to dossier_minimum.*

## Summary

(TODO: summary from captured sources)

## Key Metrics

(TODO: quantitative data from sources)

## Role in Value Chain

(TODO: supplies-to / depends-on / competes-with relationships)

## Open Questions

(TODO: gaps and deepening targets)
"""
    path.write_text(content, encoding="utf-8")
    return path

def write_brief(folder: Path, topic: str, parent: str, recon_id: str, entities: List[str],
                sources: List[str], gaps: List[str], tags: List[str], seed: str = "") -> Path:
    path = folder / "_brief.md"
    content = f"""---
recon_id: {recon_id}
topic: {topic}
parent: {parent}
seed: {seed}
status: active
last_run: {date.today().isoformat()}
tags: [{', '.join(tags)}]
entities: [{', '.join(entities)}]
gaps:
{chr(10).join(f'  - "{g}"' for g in gaps)}
---

# {topic}

## Findings

(Discovery pass complete. See Sources/ and Entities/ for captured material.)

## Entity Coverage

{chr(10).join(f'- [[{e}]]' for e in entities) if entities else '(no entities extracted yet)'}

## Gaps

{chr(10).join(f'- {g}' for g in gaps) if gaps else '(none identified yet)'}

## Next Legs

- Deepen top entities to dossier_minimum
- Run extraction (clerk) for structured data
- Run synthesis (analyst) for report
"""
    path.write_text(content, encoding="utf-8")
    return path

# ---------------------------------------------------------------------------
# Search vectors
# ---------------------------------------------------------------------------

def generate_search_vectors(topic: str, seed_entities: Optional[List[str]] = None) -> List[str]:
    if seed_entities is None:
        seed_entities = []
    vectors = [
        f"{topic} industry report 2025 2026",
        f"{topic} supply chain manufacturers",
        f"{topic} market size forecast",
        f"{topic} site:reuters.com OR site:bloomberg.com",
    ]
    if seed_entities:
        for entity in seed_entities[:5]:
            vectors.append(f'"{entity}" {topic}')
    return vectors

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Portable research recon")
    parser.add_argument("--topic", required=True, help="Topic name")
    parser.add_argument("--parent", default="General", help="Parent topic folder")
    parser.add_argument("--seed", default="", help="Seed URL for context")
    parser.add_argument("--seed-text", default="", help="Raw seed text")
    parser.add_argument("--seed-file", default="", help="File containing seed text")
    parser.add_argument("--output-root", default="", help="Output root directory")
    parser.add_argument("--max-sources", type=int, default=15, help="Max sources to capture")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    output_root = get_output_root(args)
    folder = output_root / slugify(args.parent, max_len=60) / slugify(args.topic, max_len=60)
    recon_id = make_recon_id(args.parent, args.topic)
    tags = ["recon", slugify(args.parent), slugify(args.topic)]

    print(f"Recon: {args.topic}")
    print(f"Parent: {args.parent}")
    print(f"Output: {folder}")
    print(f"Recon ID: {recon_id}")
    print(f"Max sources: {args.max_sources}")

    if args.dry_run:
        print("\n[DRY RUN] No files would be written.")
        return

    folder.mkdir(parents=True, exist_ok=True)

    # Seed text
    seed_text = args.seed_text
    if args.seed_file:
        seed_text = Path(args.seed_file).read_text(encoding="utf-8")
    elif args.seed:
        seed_text = extract_url_content(args.seed)

    seed_entities = []
    if seed_text:
        entities = extract_entities(seed_text)
        seed_entities = entities["companies"]
        print(f"\nSeed entities: {seed_entities}")

    # Generate search vectors
    vectors = generate_search_vectors(args.topic, seed_entities)
    print(f"\nSearch vectors ({len(vectors)}):")
    for v in vectors:
        print(f"  - {v}")

    # Discover sources
    all_results = []
    for v in vectors:
        results = hermes_search(v, limit=5)
        all_results.extend(results)
        time.sleep(0.5)  # Rate limit

    # Dedup
    existing_urls = set()
    existing_titles = []
    # Check index if it exists
    index_path = folder / ".recon_index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text())
            existing_urls = set(index.get("sources", {}).keys())
        except Exception:
            pass

    deduped = dedup_sources(all_results, existing_urls, existing_titles)
    deduped = deduped[:args.max_sources]
    print(f"\nDeduped sources: {len(deduped)}")

    # Capture sources
    captured = []
    for s in deduped:
        content = extract_url_content(s["url"]) if s.get("url") else ""
        s["content"] = content
        path = write_source_note(folder, s, recon_id, tags)
        captured.append(s)
        print(f"  Captured: {s['title'][:60]}")

    # Extract entities from all captured content
    all_text = seed_text + " " + " ".join(s.get("content", "") for s in captured)
    entities = extract_entities(all_text)
    all_entities = entities["companies"] + entities["technologies"]

    # Create entity notes
    for name in all_entities[:15]:
        write_entity_note(folder, name, "company", recon_id, tags,
                         [s["title"] for s in captured[:3]])

    # Gaps
    gaps = [
        f"Deepen {name} to dossier_minimum" for name in all_entities[:5]
    ]

    # Write brief
    write_brief(folder, args.topic, args.parent, recon_id,
                all_entities[:15], [s["title"] for s in captured],
                gaps, tags, args.seed)

    # Update index
    index = {"recons": {}, "entities": {}, "sources": {}}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text())
        except Exception:
            pass

    recon_key = slugify(f"{args.parent}-{args.topic}")
    index["recons"][recon_key] = {
        "topic": args.topic,
        "parent": args.parent,
        "folder": str(folder.relative_to(output_root)),
        "first_run": index.get("recons", {}).get(recon_key, {}).get("first_run", date.today().isoformat()),
        "last_run": date.today().isoformat(),
        "entity_count": len(all_entities[:15]),
        "source_count": len(captured),
        "status": "active",
    }
    for s in captured:
        if s.get("url"):
            index["sources"][s["url"]] = {"title": s.get("title", ""), "recon": recon_key}
    for e in all_entities[:15]:
        index["entities"][e] = {"type": "company", "recon": recon_key}

    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Recon complete: {args.topic}")
    print(f"Sources captured: {len(captured)}")
    print(f"Entities discovered: {len(all_entities[:15])}")
    print(f"Output: {folder}")
    print(f"\nNext steps:")
    print(f"  1. Review Entities/ and deepen top candidates")
    print(f"  2. Run extraction (clerk) for structured JSON")
    print(f"  3. Run synthesis (analyst) for _report.md")

if __name__ == "__main__":
    main()
