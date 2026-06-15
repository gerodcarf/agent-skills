#!/usr/bin/env python3
import os
import sys
import json
import re
import argparse
import subprocess
import requests
from pathlib import Path

# standard English stop words
STOP_WORDS = {
    "the", "and", "a", "of", "to", "in", "is", "for", "on", "with", "as", "by", "an", "at", 
    "through", "that", "this", "from", "it", "its", "are", "be", "or", "which", "was",
    "were", "but", "not", "he", "she", "they", "we", "you", "i", "how", "what", "where",
    "when", "why", "who", "which", "lens", "recent", "dynamics", "alternatives", "expiries",
    "evaluating", "evaluate", "potential", "impacts", "impact", "trends", "outlook", "status",
    "analysis", "challenges", "opportunities", "transition", "developments", "development",
    "technology", "technologies"
}

def extract_keywords(goal_text: str) -> list[str]:
    # Clean text, remove punctuation, split into lowercase words
    cleaned = re.sub(r'[^a-zA-Z0-9\s-]', ' ', goal_text)
    words = cleaned.split()
    keywords = []
    seen = set()
    for w in words:
        wl = w.lower()
        if len(wl) > 2 and wl not in STOP_WORDS and wl not in seen:
            seen.add(wl)
            keywords.append(w) # Keep original casing (or capitalisation)
    return keywords[:6] # Limit to top 6 keywords to keep query focused

def load_dot_env():
    env_path = Path("/Users/ambler/.hermes/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

def query_hindsight(keywords: list[str]) -> str:
    hindsight_url = os.environ.get("HINDSIGHT_URL")
    if not hindsight_url:
         return "<!-- Hindsight URL not set in environment -->\n"
    
    try:
        from hindsight_client import Hindsight
        client = Hindsight(base_url=hindsight_url)
        
        # We query with concatenated keywords
        query = " ".join(keywords)
        resp = client.recall(bank_id="hermes", query=query, include_entities=True, include_chunks=True)
        
        if hasattr(resp, "to_prompt_string"):
            return getattr(resp, "to_prompt_string")()
        else:
            return f"<!-- Hindsight response: {str(resp)} -->\n"
    except ImportError:
        return "<!-- hindsight_client library not installed in this environment -->\n"
    except Exception as e:
        return f"<!-- Error querying Hindsight: {str(e)} -->\n"

def query_neo4j(keywords: list[str]) -> str:
    # Resolve host
    neo4j_url = "http://boreas.cow-hippocampus.ts.net:7474/db/neo4j/tx/commit"
    passw = os.environ.get("NEO4J_PASSWORD")
    user = os.environ.get("NEO4J_USER", "neo4j")
    
    if not passw:
        return "<!-- Neo4j password not set in environment -->\n"
        
    output = []
    
    try:
        # Build keyword-based regex or queries
        node_clauses = []
        rel_clauses = []
        for kw in keywords:
            escaped = kw.replace("'", "\\'")
            node_clauses.append(f"n.name =~ '(?i).*{escaped}.*' OR n.title =~ '(?i).*{escaped}.*' OR n.ticker =~ '(?i).*{escaped}.*'")
            rel_clauses.append(f"a.name =~ '(?i).*{escaped}.*' OR b.name =~ '(?i).*{escaped}.*'")
            
        node_where = " OR ".join(node_clauses)
        rel_where = " OR ".join(rel_clauses)
        
        # 1. Query nodes
        node_query = f"MATCH (n) WHERE {node_where} RETURN labels(n) as labels, properties(n) as props LIMIT 25"
        payload = {"statements": [{"statement": node_query}]}
        res = requests.post(neo4j_url, auth=(user, passw), json=payload, timeout=15)
        
        if res.status_code == 200:
            nodes_data = res.json().get("results", [])[0].get("data", [])
            if nodes_data:
                output.append("### Neo4j Entity Matches")
                output.append("| Label | Name | Key Properties |")
                output.append("|---|---|---|")
                for item in nodes_data:
                    row = item.get("row", [])
                    if len(row) >= 2:
                        labels = ", ".join(row[0])
                        props = row[1]
                        name = props.get("name") or props.get("title") or props.get("id") or "Unnamed"
                        # Extract some interesting properties
                        interesting = {k: v for k, v in props.items() if k not in ["name", "title", "created_at", "enriched_at"]}
                        props_str = ", ".join(f"`{k}`: {v}" for k, v in interesting.items() if v is not None)
                        output.append(f"| {labels} | **{name}** | {props_str} |")
                output.append("")
            else:
                output.append("<!-- No matching entities found in Neo4j -->\n")
        else:
            output.append(f"<!-- Neo4j node query returned HTTP {res.status_code} -->\n")
            
        # 2. Query relationships
        rel_query = f"MATCH (a)-[r]->(b) WHERE {rel_where} RETURN labels(a) as a_labels, a.name as a_name, type(r) as r_type, labels(b) as b_labels, b.name as b_name LIMIT 30"
        payload_rel = {"statements": [{"statement": rel_query}]}
        res_rel = requests.post(neo4j_url, auth=(user, passw), json=payload_rel, timeout=15)
        
        if res_rel.status_code == 200:
            rels_data = res_rel.json().get("results", [])[0].get("data", [])
            if rels_data:
                output.append("### Neo4j Supply Chain & Relationship Graph")
                output.append("| Source Entity | Relation | Target Entity |")
                output.append("|---|---|---|")
                for item in rels_data:
                    row = item.get("row", [])
                    if len(row) >= 5:
                        a_name = row[1]
                        r_type = row[2]
                        b_name = row[4]
                        output.append(f"| **{a_name}** ({', '.join(row[0])}) | `{r_type}` | **{b_name}** ({', '.join(row[3])}) |")
                output.append("")
            else:
                output.append("<!-- No matching relationships found in Neo4j -->\n")
        else:
            output.append(f"<!-- Neo4j relation query returned HTTP {res_rel.status_code} -->\n")
            
    except Exception as e:
        output.append(f"<!-- Error querying Neo4j: {str(e)} -->\n")
        
    return "\n".join(output)

def query_obsidian(keywords: list[str]) -> str:
    vault_path = "/Users/ambler/Obsidian/main-vault"
    if not os.path.exists(vault_path):
        return "<!-- Obsidian vault not found -->\n"
        
    output = []
    
    # 1. Search notes by title match
    title_matches = []
    for root, dirs, files in os.walk(vault_path):
        for f in files:
            if f.endswith(".md"):
                # Check if any keyword matches
                if any(kw.lower() in f.lower() for kw in keywords):
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, vault_path)
                    title_matches.append(rel_p)
                    
    if title_matches:
        output.append("### Obsidian Notes (Filename Matches)")
        for tm in sorted(title_matches)[:15]:
            output.append(f"- [[{tm[:-3]}]] (Path: `{tm}`)")
        output.append("")
        
    # 2. Search notes elements via ripgrep
    try:
        content_matches = {}
        for kw in keywords:
            cmd = ["rg", "-i", "-n", "--max-count", "3", kw, vault_path]
            try:
                res = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
                for line in res.splitlines():
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        filepath = parts[0]
                        line_num = parts[1]
                        text_match = parts[2].strip()
                        rel_path = os.path.relpath(filepath, vault_path)
                        
                        # Exclude templates, archives, or json files if appropriate
                        if rel_path.endswith(".json") or ".sync-conflict" in rel_path or ".DS_Store" in rel_path:
                            continue
                            
                        if rel_path not in content_matches:
                            content_matches[rel_path] = []
                        content_matches[rel_path].append((line_num, text_match))
            except subprocess.CalledProcessError:
                # Ripgrep exits 1 if no matches found
                continue
                
        if content_matches:
            output.append("### Obsidian Notes Content Excerpts")
            # Limit to top 8 files to prevent text flood
            for idx, (rel_path, matches) in enumerate(sorted(content_matches.items())):
                if idx >= 8:
                    break
                output.append(f"#### [[{rel_path[:-3]}]]")
                for line_num, text in matches[:3]:
                    # Escape brackets/markdown markers slightly if needed, keeping readable
                    cleaned_text = text.replace("[[", "\\[\\[").replace("]]", "\\]\\]")
                    output.append(f"- **Line {line_num}**: {cleaned_text}")
            output.append("")
    except Exception as e:
        output.append(f"<!-- Error running ripgrep search in Obsidian: {str(e)} -->\n")
        
    return "\n".join(output)

def query_bookshelf(keywords: list[str]) -> str:
    books_dir = "/Users/ambler/Bookshelf"
    reg_path = os.path.join(books_dir, "pageindex_registry.json")
    if not os.path.exists(reg_path):
        return "<!-- Bookshelf PageIndex registry not found -->\n"
        
    output = []
    
    try:
        with open(reg_path) as f:
            registry = json.load(f)
            
        matching_docs = []
        for doc in registry.get("docs", []):
            pdf_path = doc.get("pdf_path", "")
            domain = doc.get("domain", "")
            
            # Check matches in path or domain
            matches = False
            for kw in keywords:
                if kw.lower() in pdf_path.lower() or kw.lower() in domain.lower():
                    matches = True
                    break
            
            # Wait, check if the structure file has matching chapter summaries as well
            struct_rel = doc.get("structure_path")
            struct_full = os.path.join(books_dir, struct_rel) if struct_rel else None
            
            # If we don't have a direct name match, let's look at chapter summaries in its structure json
            headings = []
            general_summary_text = ""
            if struct_full and os.path.exists(struct_full):
                try:
                    with open(struct_full) as sf:
                        struct_data = json.load(sf)
                        struct_list = struct_data.get("structure", [])
                        for node in struct_list:
                            # Search summary and titles
                            title = node.get("title", "")
                            summary = node.get("summary", "")
                            
                            # Search in subnodes
                            sub_matches = False
                            for subnode in node.get("nodes", []):
                                sub_title = subnode.get("title", "")
                                sub_summary = subnode.get("summary", "")
                                if any(kw.lower() in sub_title.lower() or kw.lower() in (sub_summary or "").lower() for kw in keywords):
                                    sub_matches = True
                                    headings.append(f"{title} -> {sub_title}")
                            
                            if any(kw.lower() in title.lower() or kw.lower() in (summary or "").lower() for kw in keywords) or sub_matches:
                                matches = True
                                if summary:
                                    general_summary_text = summary
                                    break
                except Exception:
                    pass
                    
            if matches:
                matching_docs.append({
                    "pdf": pdf_path,
                    "domain": domain,
                    "structure_full": struct_full,
                    "headings": headings,
                    "summary": general_summary_text
                })
                
        if matching_docs:
            output.append("### Bookshelf PageIndex Matches")
            for m_doc in matching_docs[:10]:
                output.append(f"#### PDF: `{m_doc['pdf']}`")
                output.append(f"- **Domain**: {m_doc['domain']}")
                if m_doc['summary']:
                    clean_summary = m_doc['summary'].strip()
                    # Add indent
                    summary_indented = "\n".join("  " + l for l in clean_summary.splitlines())
                    output.append(f"- **Summary**:\n{summary_indented}")
                if m_doc['headings']:
                    output.append(f"- **Matching Chapters**: {', '.join(m_doc['headings'])}")
                output.append("")
        else:
            output.append("<!-- No matching documents found in PageIndex registry -->\n")
            
    except Exception as e:
        output.append(f"<!-- Error querying Bookshelf PageIndex: {str(e)} -->\n")
        
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description="Compiler for librarian context feeder.")
    parser.add_argument("--goal", required=True, help="Active research goal/question")
    parser.add_argument("--workspace-dir", required=True, help="Shared workspace path where report is generated")
    parser.add_argument("--query", help="Explicit query keywords (space-delimited)")
    args = parser.parse_args()
    
    workspace = Path(args.workspace_dir).expanduser()
    if not workspace.exists():
        sys.exit(f"Workspace path does not exist: {workspace}")
        
    print(f"Goal: {args.goal}")
    
    # Load env variables (for Credentials, URLs)
    load_dot_env()
    
    # Extract keywords
    if args.query:
        keywords = args.query.strip().split()
    else:
        keywords = extract_keywords(args.goal)
        
    print(f"Extracted search keywords: {keywords}")
    
    # Build context content
    sections = []
    sections.append("# KOS Context compilation (`kos_context.md`)")
    sections.append(f"Compiled context for search query keywords: {', '.join(keywords)}")
    sections.append(f"Origin Swarm Goal: {args.goal}\n")
    
    print("Querying Hindsight...")
    hs_section = query_hindsight(keywords)
    sections.append("## Hindsight Memory Records")
    sections.append(hs_section if hs_section.strip() else "*No hindsight memory records returned for the query.*")
    sections.append("")
    
    print("Querying Neo4j...")
    n4j_section = query_neo4j(keywords)
    sections.append("## Neo4j Graph Knowledge")
    sections.append(n4j_section if n4j_section.strip() else "*No Neo4j nodes or supply chains matched the query keywords.*")
    sections.append("")
    
    print("Querying Obsidian...")
    obs_section = query_obsidian(keywords)
    sections.append("## Local Obsidian Vault Notes")
    sections.append(obs_section if obs_section.strip() else "*No local Obsidian notes matched the query keywords.*")
    sections.append("")
    
    print("Querying Bookshelf...")
    bk_section = query_bookshelf(keywords)
    sections.append("## Bookshelf PageIndex Documents")
    sections.append(bk_section if bk_section.strip() else "*No Bookshelf PageIndex summaries matched the query keywords.*")
    sections.append("")
    
    master_context = "\n".join(sections)
    
    # Write output file to workspace
    out_file = workspace / "kos_context.md"
    out_file.write_text(master_context)
    print(f"Successfully compiled and wrote context to {out_file.resolve()}")
    sys.exit(0)

if __name__ == "__main__":
    main()
