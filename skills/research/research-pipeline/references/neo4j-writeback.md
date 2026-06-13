# Neo4j Knowledge Graph Writeback

The research pipeline feeds structured extraction data into Neo4j as a knowledge graph. This reference defines the Cypher patterns, provenance contract, and validation queries.

## Connection

| Variable | Usage |
|----------|-------|
| `NEO4J_URI` | Bolt connection URI (e.g., `bolt+s://host:7687`) |
| `NEO4J_URL` | HTTPS endpoint (e.g., `https://host:7474/db/neo4j/tx/commit`) |
| `NEO4J_USER` | Username (typically `neo4j`) |
| `NEO4J_PASSWORD` | Password |

Always use `NEO4J_URI` for bolt driver connections and `NEO4J_URL` for HTTPS/REST. Do not use raw HTTP on port 7474 — deprecated.

## Node Creation Patterns

### Organization

```cypher
MERGE (o:Organization {name: $name})
SET o.type = coalesce(o.type, $type),
    o.geography = coalesce(o.geography, $geography),
    o.role_in_value_chain = $role,
    o.chokepoint = $chokepoint,
    o.provenance = $provenance,
    o.source_topic = $topic,
    o.last_updated = date(),
    o.classification_confidence = $confidence
```

### Technology

```cypher
MERGE (t:Technology {name: $name})
SET t.category = $category,
    t.maturity = $maturity,
    t.provenance = $provenance,
    t.source_topic = $topic,
    t.last_updated = date()
```

### Person

```cypher
MERGE (p:Person {name: $name})
SET p.role = $role,
    p.affiliation = $affiliation,
    p.provenance = $provenance,
    t.source_topic = $topic,
    p.last_updated = date()
```

### Concept / Policy

```cypher
MERGE (c:Concept {name: $name})
SET c.category = $category,
    c.description = $description,
    c.provenance = $provenance,
    c.source_topic = $topic,
    c.last_updated = date()
```

## Relationship Patterns

```cypher
// Supply chain
MATCH (a {name: $source}), (b {name: $target})
MERGE (a)-[r:supplies_to]->(b)
SET r.confidence = $confidence,
    r.source_topic = $topic,
    r.evidence = $evidence

// Competition
MATCH (a {name: $source}), (b {name: $target})
MERGE (a)-[r:competes_with]->(b)
SET r.confidence = $confidence, r.source_topic = $topic

// Dependency
MATCH (a {name: $source}), (b {name: $target})
MERGE (a)-[r:depends_on]->(b)
SET r.confidence = $confidence, r.source_topic = $topic

// Control (chokepoint)
MATCH (a {name: $source}), (b {name: $target})
MERGE (a)-[r:controls_supply_of]->(b)
SET r.confidence = $confidence, r.source_topic = $topic

// JV / Partnership
MATCH (a {name: $source}), (b {name: $target})
MERGE (a)-[r:partner_with]->(b)
SET r.confidence = $confidence, r.source_topic = $topic
```

## Provenance Rules

1. **Never downgrade provenance.** If a node already has `provenance: "curated"`, a pipeline writeback with `provenance: "pipeline-extracted"` must NOT overwrite it. Use `coalesce()` or conditional SET.

```cypher
// Safe provenance update — only set if not already higher-trust
SET o.provenance = CASE
    WHEN o.provenance IN ['curated', 'spider-validated'] THEN o.provenance
    ELSE $provenance
END
```

2. **Pipeline-extracted is medium trust.** Always set unless the entity was manually curated or passed the full spider validation pipeline.

3. **Unverified entities never enter the graph.** junkyard-scout output stays as candidate text in card comments or `_brief.md` — never written to Neo4j.

## Metric Attachment

When the extraction JSON includes metrics, attach them as properties:

```cypher
MATCH (o:Organization {name: $name})
SET o.market_share_pct = $market_share,
    o.capacity = $capacity,
    o.capacity_unit = $unit,
    o.metric_date = $date,
    o.metric_source = $source_ref
```

For time-series metrics, use a separate Metric node:

```cypher
CREATE (m:Metric {
    type: $metric_type,
    value: $value,
    unit: $unit,
    date: date($date),
    source: $source_ref
})
WITH m, o
MATCH (o:Organization {name: $name})
CREATE (o)-[:HAS_METRIC]->(m)
```

## Validation Queries

After a writeback batch, verify:

```cypher
// Count nodes by provenance for this topic
MATCH (n {source_topic: $topic})
RETURN labels(n)[0] AS type, n.provenance AS provenance, count(*) AS count
ORDER BY type, provenance

// Check for orphan relationships (no matching nodes)
MATCH ()-[r {source_topic: $topic}]->()
WHERE NOT EXISTS { MATCH (a)-[r]->(b) WHERE a.name IS NOT NULL AND b.name IS NOT NULL }
RETURN count(*) AS orphans

// Verify no provenance downgrades occurred
MATCH (n {source_topic: $topic})
WHERE n.provenance = 'pipeline-extracted'
  AND EXISTS { MATCH (m {name: n.name}) WHERE m.provenance IN ['curated', 'spider-validated'] }
RETURN n.name AS downgraded
```

## Integration with PageIndex

The Neo4j graph is enriched by the PageIndex pipeline for PDF-backed sources:

1. PDFs staged in `~/Research/__Inbound/` → `process_inbound.py` → PageIndex enrichment
2. PageIndex extracts entities, metrics, and relationships from PDF text
3. These flow into Neo4j with `provenance: "curated"` (via the scout→clerk→analyst pipeline)
4. Pipeline-extracted entities from web sources supplement but do not override PageIndex-sourced data

## Conflict Handling

When pipeline extraction conflicts with existing KG data:

1. **Don't overwrite.** Create a `:DISPUTE` relationship or add an `in_dispute: true` flag.
2. **Record both values.** Keep the existing value as primary, add the conflicting value as a property with `_disputed` suffix.
3. **Flag for review.** Add to `_deepening_queue.md` with conflict description.
4. **Human gate.** Material conflicts (investment-relevant metrics, chokepoint status) require human resolution.

```cypher
// Example: conflict on market share
MATCH (o:Organization {name: $name})
SET o.market_share_pct = CASE
    WHEN o.market_share_pct IS NULL THEN $value
    ELSE o.market_share_pct  -- keep existing
END,
o.market_share_pct_disputed = $value,
o.in_dispute = true
```
