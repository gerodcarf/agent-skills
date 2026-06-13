#!/usr/bin/env python3
"""
Portable report generator — synthesizes captured research into a structured report.

Reads _brief.md, Sources/, and Entities/ from a recon folder and generates
_report.md with BLUF, key findings, needle-movers, and open questions.

Usage:
    python3 scripts/report.py \
        --topic "topic-slug" \
        --parent "parent-slug" \
        --output-root "$OUTPUT_ROOT"

Environment variables:
    OUTPUT_ROOT         Default output root
    OPENROUTER_API_KEY  Optional LLM key for synthesis enhancement
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

def slugify(s: str, max_len: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower())
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s[:max_len].rstrip("-")

# ---------------------------------------------------------------------------
# Reading captured material
# ---------------------------------------------------------------------------

def read_brief(folder: Path) -> Optional[dict]:
    """Parse _brief.md frontmatter."""
    brief_path = folder / "_brief.md"
    if not brief_path.exists():
        return None
    content = brief_path.read_text(encoding="utf-8")
    # Parse YAML frontmatter
    fm = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            fm_text = content[3:end].strip()
            for line in fm_text.split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    fm[key.strip()] = val.strip()
    fm["_body"] = content
    return fm

def read_sources(folder: Path) -> List[dict]:
    """Read all source notes."""
    sources_dir = folder / "Sources"
    if not sources_dir.exists():
        return []
    sources = []
    for path in sorted(sources_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        fm = {}
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                for line in content[3:end].strip().split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        fm[key.strip()] = val.strip()
        sources.append({
            "path": str(path),
            "filename": path.stem,
            "frontmatter": fm,
            "body": content,
            "word_count": len(content.split()),
        })
    return sources

def read_entities(folder: Path) -> List[dict]:
    """Read all entity notes."""
    entities_dir = folder / "Entities"
    if not entities_dir.exists():
        return []
    entities = []
    for path in sorted(entities_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        fm = {}
        status = "stub"
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                for line in content[3:end].strip().split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        fm[key.strip()] = val.strip()
                        if key.strip() == "status":
                            status = val.strip()
        entities.append({
            "name": path.stem,
            "path": str(path),
            "frontmatter": fm,
            "status": status,
            "word_count": len(content.split()),
        })
    return entities

def read_extraction(folder: Path) -> Optional[dict]:
    """Read _extraction.json if it exists."""
    path = folder / "_extraction.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def classify_confidence(source_count: int, entity_count: int, avg_entity_words: float) -> str:
    """Classify overall confidence of the report."""
    score = 0
    if source_count >= 8:
        score += 2
    elif source_count >= 4:
        score += 1
    if entity_count >= 8:
        score += 2
    elif entity_count >= 4:
        score += 1
    if avg_entity_words >= 500:
        score += 2
    elif avg_entity_words >= 200:
        score += 1
    if score >= 5:
        return "HIGH"
    elif score >= 3:
        return "MEDIUM"
    return "LOW"

def generate_report(topic: str, parent: str, folder: Path, brief: dict,
                    sources: List[dict], entities: List[dict],
                    extraction: Optional[dict]) -> str:
    """Generate _report.md content."""
    today = date.today().isoformat()
    source_count = len(sources)
    entity_count = len(entities)
    avg_entity_words = sum(e["word_count"] for e in entities) / max(entity_count, 1)
    confidence = classify_confidence(source_count, entity_count, avg_entity_words)

    # Entity status summary
    status_counts = Counter(e["status"] for e in entities)

    # Key entity names
    top_entities = sorted(entities, key=lambda e: e["word_count"], reverse=True)[:10]

    # Source titles
    source_titles = [s.get("frontmatter", {}).get("source_url", s["filename"]) for s in sources]

    # Relationships from extraction
    relationships = []
    if extraction:
        for ent in extraction.get("entities", []):
            for rel in ent.get("relationships", []):
                relationships.append(f"{ent['name']} → {rel['type']} → {rel['target']} (conf: {rel.get('confidence', 'N/A')})")

    report = f"""---
recon_id: {brief.get('recon_id', 'unknown')}
topic: {topic}
parent: {parent}
generated: {today}
source_count: {source_count}
entity_count: {entity_count}
confidence: {confidence}
tags: [recon, report, {slugify(parent)}, {slugify(topic)}]
---

# Research Report: {brief.get('topic', topic)}

> [!info] Report Metadata
> **Generated:** {today}
> **Confidence:** {confidence}
> **Sources:** {source_count} | **Entities:** {entity_count}
> **Entity Coverage:** {dict(status_counts)}

## Executive Summary (BLUF)

*Auto-generated from captured material. Review and edit.*

This report synthesizes {source_count} sources and {entity_count} entities captured for **{brief.get('topic', topic)}** under **{parent}**.

"""
    if source_count < 4:
        report += "> [!warning] Low Source Count\n> Fewer than 4 sources captured. Findings should be treated as preliminary.\n\n"
    if avg_entity_words < 200:
        report += "> [!warning] Shallow Entities\n> Average entity note is under 200 words. Deepen before drawing conclusions.\n\n"

    report += f"""## Key Findings

### Source Coverage

| # | Source | Type | Status |
|---|--------|------|--------|
"""
    for i, s in enumerate(sources[:15], 1):
        url = s.get("frontmatter", {}).get("source_url", "")
        stype = s.get("frontmatter", {}).get("type", "article")
        status = s.get("frontmatter", {}).get("ingestion_status", "captured")
        report += f"| {i} | [{s['filename'][:50]}]({url}) | {stype} | {status} |\n"

    report += f"""
### Entity Landscape

| Entity | Type | Status | Words | Key? |
|--------|------|--------|-------|------|
"""
    for e in entities[:15]:
        etype = e.get("frontmatter", {}).get("type", "unknown")
        is_key = "★" if e["word_count"] > 400 else ""
        report += f"| [[{e['name']}]] | {etype} | {e['status']} | {e['word_count']} | {is_key} |\n"

    # Relationships
    if relationships:
        report += f"""
### Extracted Relationships

| Relationship | Confidence |
|-------------|------------|
"""
        for rel in relationships[:20]:
            report += f"| {rel} |\n"

    report += f"""
## Needle-Movers

*Factors that could shift the landscape. Ranked by potential impact.*

"""
    # Pull from gaps in brief
    gaps_text = brief.get("_body", "")
    gap_section = re.search(r'## Gaps\s*\n(.*?)(?=\n## |\Z)', gaps_text, re.S)
    if gap_section:
        for line in gap_section.group(1).strip().split("\n"):
            line = line.strip("- ").strip()
            if line and not line.startswith("("):
                report += f"1. {line}\n"

    report += f"""
## Constraints & Risks

- **Source breadth:** {source_count} sources captured — {'sufficient for initial synthesis' if source_count >= 8 else 'INSUFFICIENT — deepen before relying on findings'}
- **Entity depth:** {avg_entity_words:.0f} avg words per entity — {'good coverage' if avg_entity_words >= 300 else 'needs deepening'}
- **Geographic concentration:** (analyze from entity geography fields)
- **IP/chokepoint concentration:** (analyze from chokepoint fields)

## Strategic Implications

*(To be written by analyst after review of findings. See _brief.md gaps for direction.)*

## Trading Implications

*(If applicable — tradable instruments, winners/losers. See Gray Rhino scenario integration.)*

## Open Questions

"""
    if gap_section:
        for line in gap_section.group(1).strip().split("\n"):
            line = line.strip("- ").strip()
            if line and not line.startswith("("):
                report += f"- {line}\n"
    else:
        report += "- What are the key chokepoints in this value chain?\n- Who controls supply vs. who depends on it?\n"

    report += f"""
## Confidence Assessment

- **Overall:** {confidence}
- **Source diversity:** {source_count} sources from {'multiple' if source_count >= 5 else 'limited'} origins
- **Entity depth:** {status_counts.get('dossier_minimum', 0)} at dossier_minimum, {status_counts.get('well-covered', 0)} well-covered, {status_counts.get('partial', 0)} partial, {status_counts.get('stub', entity_count)} stubs
- **Extraction coverage:** {'Clerk extraction complete' if extraction else 'No structured extraction yet'}

---

*Generated by research-pipeline report.py on {today}. Review and edit before promoting to canonical Knowledge.*
"""
    return report

# ---------------------------------------------------------------------------
# Deepening queue
# ---------------------------------------------------------------------------

def generate_deepening_queue(entities: List[dict]) -> str:
    """Generate _deepening_queue.md."""
    today = date.today().isoformat()

    # Sort by word count ascending (shallowest first = highest priority)
    sorted_entities = sorted(entities, key=lambda e: e["word_count"])

    queue = f"""---
generated: {today}
type: deepening-queue
---

# Deepening Queue

Prioritized list of entities needing deeper research. Sorted by gap size (shallowest first).

## Priority Queue

| # | Entity | Status | Words | Action |
|---|--------|--------|-------|--------|
"""
    for i, e in enumerate(sorted_entities[:20], 1):
        if e["word_count"] < 200:
            action = "→ dossier_minimum"
        elif e["word_count"] < 500:
            action = "→ well-covered"
        else:
            action = "✓ adequate"
        queue += f"| {i} | [[{e['name']}]] | {e['status']} | {e['word_count']} | {action} |\n"

    queue += f"""
## Criteria

- **dossier_minimum** (≥500 words): bottom-line judgment, products, customers, geography, dependencies, chokepoint assessment, citations
- **well-covered** (≥300 words): substantive content with source citations
- **partial** (≥100 words): basic facts and context
- **stub** (<100 words): placeholder only

*Generated by research-pipeline on {today}.*
"""
    return queue

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate research report")
    parser.add_argument("--topic", required=True, help="Topic folder slug")
    parser.add_argument("--parent", default="General", help="Parent topic folder slug")
    parser.add_argument("--output-root", default="", help="Output root directory")
    args = parser.parse_args()

    output_root = get_output_root(args)
    folder = output_root / slugify(args.parent) / slugify(args.topic)

    if not folder.exists():
        print(f"Error: Topic folder not found: {folder}")
        sys.exit(1)

    print(f"Reading from: {folder}")

    brief = read_brief(folder)
    if not brief:
        print("Warning: No _brief.md found. Creating minimal report.")

    sources = read_sources(folder)
    entities = read_entities(folder)
    extraction = read_extraction(folder)

    print(f"Sources: {len(sources)}")
    print(f"Entities: {len(entities)}")
    print(f"Extraction: {'yes' if extraction else 'no'}")

    # Generate report
    report = generate_report(args.topic, args.parent, folder, brief or {}, sources, entities, extraction)
    report_path = folder / "_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport written: {report_path}")

    # Generate deepening queue
    if entities:
        queue = generate_deepening_queue(entities)
        queue_path = folder / "_deepening_queue.md"
        queue_path.write_text(queue, encoding="utf-8")
        print(f"Deepening queue: {queue_path}")

    print(f"\n{'='*60}")
    print(f"Report generation complete.")
    print(f"Confidence: {classify_confidence(len(sources), len(entities), sum(e['word_count'] for e in entities)/max(len(entities),1))}")
    print(f"\nNext steps:")
    print(f"  1. Review and edit _report.md")
    print(f"  2. Deepen entities from _deepening_queue.md")
    print(f"  3. Run Neo4j writeback if extraction data exists")

if __name__ == "__main__":
    main()
