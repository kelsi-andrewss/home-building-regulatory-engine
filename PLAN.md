# Home Building Regulatory Engine — Project Plan

## Goal

Given a residential parcel in the City of Los Angeles, produce an evidence-backed buildability assessment: what can be built, with what confidence, citing which regulations.

## Architecture

```
                          ┌─────────────────────────┐
                          │      React Frontend      │
                          │  (Vite + TypeScript)      │
                          │                           │
                          │  ┌─────────┐ ┌─────────┐ │
                          │  │ Address │ │  Map    │ │
                          │  │ Search  │ │(Mapbox) │ │
                          │  └────┬────┘ └────┬────┘ │
                          │       │           │       │
                          │  ┌────▼───────────▼────┐ │
                          │  │ Buildability Report  │ │
                          │  │ + Confidence Badges  │ │
                          │  │ + Citations Panel    │ │
                          │  │ + Chat Follow-up     │ │
                          │  └─────────────────────┘ │
                          └────────────┬──────────────┘
                                       │ REST API
                          ┌────────────▼──────────────┐
                          │     FastAPI Backend        │
                          │                            │
                          │  ┌──────────────────────┐  │
                          │  │   Parcel Service      │  │
                          │  │  CAMS Geocoder →      │  │
                          │  │  County Parcel API →  │  │
                          │  │  NavigateLA Zoning    │  │
                          │  └──────────┬───────────┘  │
                          │             │              │
                          │  ┌──────────▼───────────┐  │
                          │  │  Regulatory Ingestion │  │
                          │  │  Pipeline             │  │
                          │  │  PDF → LLM → struct   │  │
                          │  │  rule fragments       │  │
                          │  └──────────┬───────────┘  │
                          │             │              │
                          │  ┌──────────▼───────────┐  │
                          │  │   Rule Engine         │  │
                          │  │  Base zone rules      │  │
                          │  │  + Specific plans     │  │
                          │  │  + ADU state law      │  │
                          │  │  + Overlay modifiers  │  │
                          │  └──────────┬───────────┘  │
                          │             │              │
                          │  ┌──────────▼───────────┐  │
                          │  │   LLM Synthesis       │  │
                          │  │  Claude API           │  │
                          │  │  Interpretation +     │  │
                          │  │  Explanation +        │  │
                          │  │  Chat follow-up       │  │
                          │  └─────────────────────┘  │
                          │                            │
                          │  ┌─────────────────────┐   │
                          │  │  PostgreSQL/PostGIS  │   │
                          │  │  Cached parcels +    │   │
                          │  │  Structured rules +  │   │
                          │  │  Ingested regs +     │   │
                          │  │  Assessment history  │   │
                          │  └─────────────────────┘   │
                          └────────────────────────────┘
```

## Regulatory Ingestion Pipeline

The core differentiator. Transforms raw regulatory documents (PDFs, zoning code text) into structured, queryable rule fragments using LLM processing.

### Pipeline Steps

1. **Collect** — Download all ~40 LA City specific plan PDFs + base zoning code sections from LA City Planning
2. **Extract** — PDF → text extraction (PyMuPDF/pdfplumber)
3. **Structure** — Feed text to Claude with a structured output schema. For each document, extract:
   - Dimensional constraints (setbacks, height, FAR, lot coverage, density)
   - Use restrictions (permitted, conditional, prohibited)
   - Design standards (if any)
   - Special triggers (e.g., "additions over 900 cumulative sf require design review")
   - Override behavior (does this replace base zone rules, or apply "whichever is more restrictive"?)
4. **Store** — Write structured rule fragments to PostgreSQL with:
   - `source_document`: filename, URL, section, page number
   - `zone_applicability`: which zones this rule applies to (or "all zones in specific plan area")
   - `constraint_type`: setback_front, setback_side, setback_rear, height_max, far_max, density, lot_coverage, etc.
   - `value`, `unit`, `condition` (e.g., "if lot > 10,000 sf")
   - `confidence`: "interpreted" (AI-extracted, pending human verification)
   - `extraction_reasoning`: why the LLM interpreted the rule this way
5. **Validate** — Run consistency checks: do extracted values fall within plausible ranges? Flag outliers for review.
6. **Promote** — Human reviews AI-extracted rules. Confidence upgraded from "interpreted" → "verified" upon confirmation.

### Output Schema (per rule fragment)

```json
{
  "id": "uuid",
  "source": {
    "document": "Mulholland Scenic Parkway Specific Plan",
    "url": "https://planning.lacity.gov/...",
    "section": "Section 7.B",
    "page": 12
  },
  "zone_applicability": ["all"],
  "specific_plan": "Mulholland Scenic Parkway",
  "constraint_type": "height_max",
  "value": 40,
  "unit": "ft",
  "condition": null,
  "overrides_base_zone": true,
  "confidence": "interpreted",
  "extraction_reasoning": "Section 7.B states 'No building or structure shall exceed forty (40) feet in height' — this is an absolute cap that replaces the base zone height limit.",
  "extracted_at": "2026-04-01T12:00:00Z"
}
```

### Documents to Ingest

- **Base zoning code**: LAMC §§12.07.01–12.11 (RE, RS, R1, R2, RD, R3, R4) — already partially structured in this plan, but pipeline validates against source text
- **~40 Specific Plans**: Each a PDF from LA City Planning (Mulholland, Venice Coastal, Brentwood, Warner Center, etc.)
- **ADU ordinance**: LA City's local ADU ordinance + CA Gov. Code §65852.2
- **Baseline Hillside Ordinance (BHO)**: Separate set of rules for hillside parcels
- **Community Plan land use policies**: General plan context per community plan area

## Data Sources (All Free, No Auth Required)

| Step | Endpoint | Returns |
|------|----------|---------|
| Address → lat/lng | `geocode.gis.lacounty.gov/.../CAMS_Locator/GeocodeServer/findAddressCandidates` | Coordinates (WKID 2229, reproject to WGS84) |
| lat/lng → Parcel | `public.gis.lacounty.gov/.../LACounty_Parcel/MapServer/0/query` (spatial intersect) | APN, geometry, lot data, year built, sqft, units |
| Parcel → Zoning | `maps.lacity.org/.../NavigateLA/MapServer/71/query` (spatial intersect) | ZONE_CMPLT (e.g. "R1-1"), ZONE_CLASS, ZONE_CODE |
| Parcel → Land Use | `maps.lacity.org/.../NavigateLA/MapServer/70/query` | General Plan Land Use category |
| Parcel → Specific Plans | `maps.lacity.org/.../NavigateLA/MapServer/93/query` | Specific Plan name, if any |
| Parcel → Historic Overlay | `maps.lacity.org/.../NavigateLA/MapServer/75/query` | HPOZ district name, if any |

All endpoints accept `f=geojson` for GeoJSON output.

## Zone Classification Parsing

LA zoning designations are compound: `[Zone Class]-[Height District]`

- **Zone class** (R1, R2, RD1.5, RD2, RS, RE9, R3, R4, etc.) → determines use, setbacks, density, lot requirements
- **Height district** (1, 1L, 1VL, 1XL, 1SS) → determines max height and FAR

The `ZONE_CMPLT` field from NavigateLA Layer 71 gives the full string. We parse it to derive both components.

## Regulatory Rules — PoC Scope

### Base Zone Constraints (Deterministic)

| Zone | LAMC Section | Min Lot (sf) | Min Width | Front Yard | Side Yard | Rear Yard | Max Height | Density |
|------|-------------|-------------|-----------|------------|-----------|-----------|------------|---------|
| RE9 | §12.07.01 | 9,000 | 65' | 20% depth, max 25' | 10' | 25% depth, max 25' | 33' | 1/lot |
| RE11 | §12.07.01 | 11,000 | 70' | 20% depth, max 25' | 10' | 25% depth, max 25' | 33' | 1/lot |
| RE15 | §12.07.01 | 15,000 | 80' | 20% depth, max 25' | 10' | 25% depth, max 25' | 33' | 1/lot |
| RE20 | §12.07.01 | 20,000 | 100' | 20% depth, max 25' | 10' | 25% depth, max 25' | 33' | 1/lot |
| RE40 | §12.07.01 | 40,000 | 150' | 20% depth, max 25' | 10' | 25% depth, max 25' | 33' | 1/lot |
| RS | §12.07.1 | 7,500 | 60' | 20% depth, max 25' | 5' | 20' | 33' | 1/lot |
| R1 | §12.08 | 5,000 | 50' | 20% depth, max 20' | 5' | 15' | 33' | 1/lot |
| R2 | §12.09 | 5,000 | 50' | 20% depth, max 20' | 5' | 15' | 33' | 1/2,500 sf |
| RD6 | §12.09.1 | 6,000 | 50' | 20' | 5' | 15' | 45' (HD-1) | 1/6,000 sf |
| RD5 | §12.09.1 | 5,000 | 50' | 20' | 5' | 15' | 45' (HD-1) | 1/5,000 sf |
| RD4 | §12.09.1 | 5,000 | 50' | 20' | 5-10' | 15' | 45' (HD-1) | 1/4,000 sf |
| RD3 | §12.09.1 | 5,000 | 50' | 20' | 5-10' | 15' | 45' (HD-1) | 1/3,000 sf |
| RD2 | §12.09.1 | 5,000 | 50' | 20' | 5' | 15' | 45' (HD-1) | 1/2,000 sf |
| RD1.5 | §12.09.1 | 5,000 | 50' | 20' | 5' | 15' | 45' (HD-1) | 1/1,500 sf |
| R3 | §12.10 | 5,000 | 50' | 15' | 5' | 15' | 45' (HD-1) | 1/800 sf |
| R4 | §12.11 | 5,000 | 50' | 15' | 5' | 15' | 45' (HD-1) | 1/400 sf |

### Height District Modifiers

| HD | Max Height (single-family zones) | Max Height (multi-family) | Max FAR (multi-family) |
|----|----------------------------------|---------------------------|------------------------|
| 1 | 33' | 45' | 3:1 |
| 1L | 33' | 35' | 3:1 |
| 1VL | 33' | 33' | 3:1 |
| 1XL | 33' | 30' | 3:1 |
| 1SS | 33' (1 story) | 30' (1 story) | 3:1 |

### RFAR (Single-Family Zones: RE, RS, R1)

Non-hillside R1: ~0.45 of lot area. Hillside: slope-band method (0.30-0.50).

### ADU Rules (CA State Law — Preempts Local Zoning)

| Constraint | State Minimum |
|------------|--------------|
| Setbacks (side/rear) | 4' max required |
| Height | 16' guaranteed; 18' near transit; 25' attached |
| Size floor | 800 sf guaranteed buildable |
| Max size (detached) | 1,200 sf |
| Max size (attached) | lesser of 1,200 sf or 50% of primary |
| JADU max | 500 sf (within existing structure) |
| Approval | Ministerial (no discretionary review) |
| Parking | No replacement parking required |
| Impact fees | Waived for ADUs ≤750 sf |

### Confidence Model

Three tiers for every constraint in the output:

- **Verified** — Deterministic rule from structured database. Zone = R1, setback = 5'. No interpretation needed.
- **Interpreted** — LLM-derived from zoning text or overlay interaction. E.g., "This parcel is in a Specific Plan area that may modify height limits." Includes citation and reasoning.
- **Unknown** — Insufficient data to determine. E.g., hillside status, geological hazards. Flagged for human review.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Frontend | React 18, Vite, TypeScript |
| Maps | Mapbox GL JS |
| LLM | Claude API (claude-sonnet-4-20250514) |
| Spatial lib | Shapely, GeoJSON |
| Hosting | AWS ECS Fargate (~$42/mo) |
| Container Registry | AWS ECR |
| CDN | AWS CloudFront |
| Storage | AWS S3 (regulatory PDFs + frontend build) |
| Secrets | AWS Secrets Manager |
| Load Balancer | AWS ALB + ACM cert |
| Database | AWS RDS PostgreSQL + PostGIS |

## API Design

### `POST /api/assess`
Input: `{ "address": "123 Main St, Los Angeles, CA" }` or `{ "apn": "1234-567-890" }`

Output:
```json
{
  "parcel": {
    "apn": "1234-567-890",
    "address": "123 Main St, Los Angeles, CA 90012",
    "geometry": { "type": "Polygon", "coordinates": [...] },
    "lot_area_sf": 6200,
    "lot_width_ft": 50,
    "year_built": 1952,
    "existing_units": 1,
    "existing_sqft": 1400
  },
  "zoning": {
    "zone_complete": "R1-1",
    "zone_class": "R1",
    "height_district": "1",
    "general_plan_land_use": "Low Residential",
    "specific_plan": null,
    "historic_overlay": null
  },
  "building_types": [
    {
      "type": "Single Family Home",
      "allowed": true,
      "confidence": "verified",
      "constraints": [
        {
          "name": "Max Height",
          "value": "33 ft",
          "confidence": "verified",
          "citation": "LAMC §12.08, Height District 1",
          "explanation": "R1 zones in Height District 1 are limited to 33 feet."
        },
        {
          "name": "Front Setback",
          "value": "20 ft",
          "confidence": "verified",
          "citation": "LAMC §12.08.C.1",
          "explanation": "20% of lot depth (100 ft), capped at 20 ft maximum."
        }
      ],
      "max_buildable_area_sf": 2790,
      "max_units": 1
    },
    {
      "type": "ADU",
      "allowed": true,
      "confidence": "verified",
      "constraints": [...],
      "max_size_sf": 1200,
      "notes": "State law (Gov. Code §65852.2) guarantees at least one ADU by right."
    }
  ],
  "setback_geometry": { "type": "Polygon", "coordinates": [...] },
  "summary": "This 6,200 sf R1-1 parcel can support a single-family home up to 33 ft / 2,790 sf buildable area, plus a detached ADU up to 1,200 sf with 4 ft setbacks.",
  "assessment_id": "uuid"
}
```

### `GET /api/parcel/{apn}`
Returns cached parcel data + zoning.

### `POST /api/chat`
Input: `{ "assessment_id": "uuid", "message": "Can I build a two-story ADU?" }`
Output: Streamed LLM response with citations from the assessment context.

## Phase Plan

### Phase 1 — Data Foundation + Regulatory Ingestion (Day 1-2)

- [ ] Project scaffolding: FastAPI backend, React frontend, Docker Compose, PostGIS
- [ ] Parcel service: CAMS geocoder integration, LA County Parcel API client, NavigateLA zoning query
- [ ] Address → parcel → zone pipeline working end-to-end
- [ ] PostGIS schema: parcels (cached), zones, rule_fragments, specific_plans, assessments
- [ ] Basic coordinate reprojection (WKID 2229 → WGS84)
- [ ] Regulatory ingestion pipeline: PDF text extraction + LLM structuring
- [ ] Collect all ~40 specific plan PDFs from LA City Planning
- [ ] Run ingestion pipeline: extract structured rule fragments from all specific plans
- [ ] Ingest base zoning code sections (LAMC §§12.07–12.11) for validation against hand-coded rules
- [ ] Ingest ADU ordinance + CA state ADU law
- [ ] Ingest Baseline Hillside Ordinance
- [ ] Store all rule fragments with source citations and confidence tags

### Phase 2 — Rule Engine (Day 2-4)

- [ ] Zone parser: extract zone_class + height_district from ZONE_CMPLT string
- [ ] Base zone rules as seed data (deterministic, verified confidence)
- [ ] Specific plan rule resolver: when parcel is in a specific plan area, merge ingested specific plan rules with base zone rules (most restrictive wins, unless plan explicitly overrides)
- [ ] ADU rule layer: state law constraints, preemption logic over local rules
- [ ] Rule engine: parcel + zone + overlays → full constraint set with per-constraint citations
- [ ] Setback geometry calculation using Shapely (buffer inward from parcel polygon)
- [ ] Confidence tagging on every output constraint (verified for base zones, interpreted for AI-ingested specific plans)
- [ ] LLM synthesis: take structured constraints → natural language summary with explanation

### Phase 3 — Frontend (Day 3-5)

- [ ] Address search bar with autocomplete
- [ ] Mapbox map: parcel polygon, zoning overlay, setback lines
- [ ] Building type selector: SFH, ADU, Guest House, Duplex
- [ ] Buildability report panel: constraints table with confidence badges (color-coded: verified/interpreted/unknown)
- [ ] Citations panel: expandable source references with links to source documents
- [ ] Specific plan callout: if parcel is in a specific plan, show which rules were modified and why
- [ ] Responsive layout

### Phase 4 — Polish + Bonus (Day 5-7)

- [ ] Chat follow-up interface (POST /api/chat with streaming)
- [ ] Project parameter inputs (bedrooms, bathrooms, sqft)
- [ ] User feedback mechanism (thumbs up/down per constraint — feeds back into confidence model)
- [ ] Setback geometry visualization on map (buildable envelope)
- [ ] Admin view: show ingestion pipeline status, rule fragment counts per document, confidence distribution
- [ ] Test against provided sample parcels + various building types
- [ ] Architecture diagram (production AWS topology)
- [ ] README with setup instructions

## Hosting — AWS ECS Fargate

### Architecture
```
Route 53 (DNS)
    ↓
CloudFront (CDN)
    ├── /api/* → ALB → ECS Fargate (FastAPI containers)
    │                      ↓
    │               RDS PostgreSQL + PostGIS
    │
    └── /* → S3 (React static build)

Secrets Manager → ECS task (Claude API key, Mapbox token, DB credentials)
ECR → ECS (Docker image registry)
S3 → regulatory PDFs bucket (ingestion source)
```

### AWS Services & Cost

| Service | Config | Monthly Cost |
|---------|--------|-------------|
| ECS Fargate | 0.25 vCPU, 0.5 GB RAM | ~$9/mo |
| RDS PostgreSQL | db.t3.micro, 20 GB gp3, PostGIS | ~$13/mo |
| ALB | Application Load Balancer | ~$16/mo |
| S3 | Two buckets (frontend + regulatory PDFs) | ~$0.10/mo |
| CloudFront | CDN distribution | ~$1/mo |
| ECR | Docker image storage | ~$1/mo |
| Secrets Manager | 3 secrets | ~$1.20/mo |
| ACM | SSL certificate | Free |
| Route 53 | DNS zone (optional) | $0.50/mo |
| **Total** | | **~$42/mo** |

### Deployment — Terraform IaC

All infrastructure defined in `infrastructure/terraform/`:

```
infrastructure/terraform/
├── main.tf           # provider config, state backend
├── vpc.tf            # VPC, subnets, security groups
├── ecs.tf            # cluster, task definition, service, auto-scaling
├── rds.tf            # PostgreSQL + PostGIS
├── alb.tf            # load balancer, target group, HTTPS listener
├── s3.tf             # frontend bucket, regulatory PDFs bucket
├── cloudfront.tf     # CDN distribution
├── ecr.tf            # container registry
├── secrets.tf        # Secrets Manager entries
├── outputs.tf        # ALB URL, CloudFront URL, RDS endpoint
└── variables.tf      # environment-specific config
```

Deploy: `terraform init && terraform apply`
Tear down: `terraform destroy`

Entire infrastructure is reproducible, version-controlled, and reviewable.

### Scaling
- Fargate auto-scales on CPU/memory/request count
- RDS can scale vertically (resize) or add read replicas
- CloudFront handles frontend traffic spikes
- No architecture changes needed to go from PoC → production — same stack, bigger numbers

### Production Additions (for architecture diagram)
- ElastiCache (Redis) — parcel/zone response cache
- RDS Multi-AZ — database failover
- WAF — API rate limiting and protection
- CloudWatch — monitoring, alarms, dashboards
- Multiple Fargate tasks across AZs — high availability

## Known Gaps & Risks

1. **Lot coverage %** — not confirmed from primary source for all zones. Ingestion pipeline should extract this from LAMC sections; fall back to CP-7150 PDF (manual extraction) if needed.
2. **Hillside determination** — no clear API for whether a parcel is in a hillside area. NavigateLA has geotechnical layers (IDs 118-131) that may help. May need elevation data as fallback.
3. **Ingestion accuracy** — AI-extracted rule fragments need validation. Confidence model handles this (interpreted until verified), but we should spot-check a sample of extractions against known values.
4. **Height district 1L/1VL exact heights** — confirmed structure but exact ceiling values for some sub-districts need verification during ingestion.
5. **CAMS geocoder rate limits** — no published rate limit. Cache aggressively in PostGIS.
6. **Lot dimensions** — parcel API gives area but not explicit width/depth. Derive from geometry using Shapely minimum bounding rectangle.
7. **Specific plan PDF availability** — assumes all ~40 PDFs are publicly downloadable from LA City Planning. Some may be behind login or broken links.
8. **Rule interaction complexity** — when a specific plan AND a hillside ordinance AND an HPOZ overlay all apply to the same parcel, the rule merging logic gets complex. PoC will handle the common cases; edge cases flagged as "Unknown."
