# Civic Access Index — Design Document

**Status:** Pre-implementation design
**Implementation budget:** ~120 hours
**Target outcome:** A production-shaped, public-interest geospatial data platform that demonstrates operational fluency across asynchronous ingestion, PostGIS analysis, cached APIs, search, observability, and IaC-driven AWS deployment.

---

## 1. Project Overview

### 1.1 One-sentence description

Civic Access Index is a geospatial data platform that ingests heterogeneous public datasets, normalizes them into census-tract-level access metrics, computes transparent service-gap scores, and exposes searchable APIs plus an internal dashboard for identifying underserved communities.

### 1.2 Framing

This is **not** a consumer civic-tech product, a definitive equity model, or policy advice. It is an *operational data system* — the kind of platform a research group, public health department, or civic-data nonprofit would actually run. The portfolio signal is "I can stand up a real data platform end to end," not "I made a pretty map."

Reviewers should evaluate it as infrastructure: ingestion provenance, data-quality handling, schema discipline, transparent scoring, observability, deployability. The map is a window into that system, not its purpose.

### 1.3 Anti-goals (explicit non-features)

To stay inside 120 hours, the project deliberately does **not**:

- Implement multi-tenant user accounts, role-based access, or social features.
- Make causal or policy claims; scores are descriptive composites, not impact estimates.
- Cover every public dataset; phased adapters keep scope finite.
- Replace established tools (PolicyMap, Justice40, CDC SVI). It is positioned as a *teachable* and *inspectable* alternative.
- Optimize for end-user UX polish; the dashboard is internal-tool aesthetic.
- Pursue real-time ingestion; refresh cadences are daily-or-slower.
- Implement GTFS or FCC broadband in v1 (deferred to v2 — see §27).

### 1.4 Success criteria

A reviewer running `docker compose up` should, within 10 minutes, be able to: trigger an ingestion, watch it complete in the dashboard, click a high-score Massachusetts census tract, see a transparent score breakdown with cited metric provenance, and navigate to OpenAPI docs. The Terraform plan should apply cleanly to a fresh AWS account.

---

## 2. Engineering Principles

These principles are the spine of the codebase. They resolve ambiguities and keep the implementation coherent under time pressure.

**Service-first, not script-first.** No notebooks in the repo. Even one-off operations live as Celery tasks, CLI scripts under `scripts/`, or admin endpoints. Exploration happens privately.

**Modular monolith, not microservices.** One repo, one API deployable, one worker deployable. Module boundaries are enforced by directory layout and import discipline (`ingestion/` does not import from `api/`), not by network calls.

**Ingestion runs are first-class.** Every byte that enters the database came from a recorded `ingestion_run` with a status, counts, retry state, and a raw snapshot URI. There is no "just run a script to load it."

**Provenance to the row.** Every normalized record links to its source record id and ingestion run. A reviewer should be able to answer "where did this number come from?" by clicking.

**Transparent scoring.** No black-box weights. Score formulas are constants in code, exposed in the API, and accompanied by per-tract explanation objects naming the dominant metrics and known limitations.

**Schema as contract.** Pydantic models gate every external boundary (HTTP request, HTTP response, source payload, queue message). SQLAlchemy models are the single source of truth for the database. Alembic migrations are the only way schema changes ship.

**Idempotency by default.** Ingestion is content-hash aware: re-running a source produces zero diff if upstream is unchanged. Score recomputation is replayable. Search reindexing uses alias rotation.

**Honest error handling.** Distinguish *expected partial failure* (rejected rows logged to `data_quality_issues`) from *infrastructure failure* (caught, logged with context, surfaced via `/healthz`). Never swallow an exception silently.

**Abstraction earns its place.** Repeated patterns get an abstraction (the `SourceAdapter` protocol, the `TractMetric` registry, the `cache_key` helper). One-off code stays one-off.

**Documentation lives next to the thing it documents.** Each subsystem has a `README.md` in its directory. Architecture decisions of consequence get an ADR. The `docs/` folder is for cross-cutting concerns only.

---

## 3. Technology Stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.12+ | 3.13 if AWS Lambda/Fargate base images support it cleanly. |
| Package manager | `uv` | Faster than Poetry, lockfile is portable, single-binary install. |
| Web framework | FastAPI | Async-native, OpenAPI for free, plays well with Pydantic v2. |
| Validation | Pydantic v2 | One model layer for HTTP, queue, and source-payload validation. |
| ORM | SQLAlchemy 2.0 (async) | Typed `Mapped[...]` style; `asyncpg` driver for Postgres. |
| Database | PostgreSQL 16 + PostGIS 3.4 | Single primary, read replicas not needed at this scale. |
| Migrations | Alembic | Autogenerate baseline, hand-tune for PostGIS specifics. |
| Async jobs | Celery 5 | Familiar, mature; `celery beat` for cron. |
| Broker / cache | Redis 7 | Both Celery broker and API cache. Separate logical databases. |
| Search | OpenSearch 2.x | Optional but valuable; deferred behind a feature flag. |
| HTTP client | `httpx` (async, HTTP/2) | Connection pooling, retries via `tenacity`. |
| Geospatial | GeoPandas, Shapely 2, pyproj, `geoalchemy2` | Standard PostGIS-friendly toolchain. |
| Frontend | React 18 + TypeScript + Vite | MapLibre GL JS for the map. TanStack Query for fetch caching. |
| Containerization | Docker, Docker Compose v2 | Multi-stage builds, distroless or slim base. |
| Cloud | AWS (ECS Fargate, RDS, ElastiCache, S3, CloudWatch, ALB) | One region, one VPC. |
| IaC | Terraform 1.7+ | S3 backend with DynamoDB lock, per-env workspaces. |
| CI/CD | GitHub Actions | Reusable workflows, branch protection on `main`. |
| Lint / format | `ruff` (lint + format) | Replaces black/isort/flake8/pyupgrade. |
| Type checking | `mypy --strict` on `app/` | Frontend uses `tsc --noEmit` in CI. |
| Testing | `pytest`, `pytest-asyncio`, `pytest-postgresql`, `polyfactory`, `respx` | `testcontainers` for the OpenSearch path. |
| Pre-commit | `pre-commit` with ruff, mypy, alembic check | Prevents broken `main`. |
| Secrets | AWS Secrets Manager (prod), `.env` (dev) | Loaded via `pydantic-settings`. |
| Observability | `structlog` (JSON logs), OpenTelemetry SDK, CloudWatch | Traces optional in v1; logs and metrics required. |

### 3.1 Why FastAPI over Django

Django is a strong default, but the signal here is *services and data platforms*, not server-rendered web apps. FastAPI's async-first model fits async ingestion clients, its Pydantic-native typing produces honest OpenAPI documents, and it stays out of the way of the analytical core, which is where the project's character lives.

### 3.2 Why `uv` over Poetry

Poetry is fine. `uv` is faster, has a cleaner CLI, ships as a single static binary, and is what reviewers in 2026 increasingly expect to see. Lockfile compatibility with pip means escape hatches are easy.

---

## 4. System Architecture

### 4.1 Conceptual diagram

```
                  ┌──────────────────────────────────┐
                  │  Public APIs / Datasets          │
                  │  Census ACS, TIGER, USDA,        │
                  │  CMS, OpenStreetMap (Overpass)   │
                  └─────────────────┬────────────────┘
                                    │ async fetch (httpx, tenacity)
                                    ▼
        ┌────────────────────────────────────────────────────────┐
        │  Ingestion Workers (Celery)                            │
        │  fetch → snapshot → validate → normalize → upsert      │
        └────────────┬──────────────────────────────┬────────────┘
                     │                              │
                     ▼                              ▼
        ┌────────────────────────┐   ┌──────────────────────────┐
        │  S3 Raw Snapshots      │   │  PostgreSQL + PostGIS    │
        │  content-addressed     │   │  canonical tables        │
        └────────────────────────┘   └────────────┬─────────────┘
                                                  │
                                                  ▼
                                  ┌─────────────────────────────┐
                                  │  Analysis / Scoring Engine  │
                                  │  metrics → percentiles →    │
                                  │  composite Civic Access     │
                                  │  Index + explanation JSON   │
                                  └─────────────┬───────────────┘
                                                │
                ┌───────────────────────────────┼─────────────────────────┐
                ▼                               ▼                         ▼
        ┌──────────────┐             ┌─────────────────┐         ┌────────────┐
        │  FastAPI     │             │  OpenSearch     │         │  Redis     │
        │  REST + JSON │             │  faceted search │         │  cache +   │
        │  OpenAPI     │             │  (optional)     │         │  broker    │
        └──────┬───────┘             └─────────────────┘         └────────────┘
               │
               ▼
        ┌──────────────────────────────┐
        │  React Dashboard             │
        │  MapLibre choropleth,        │
        │  filters, tract detail,      │
        │  data ops console            │
        └──────────────────────────────┘
```

### 4.2 Service boundaries

The deployable units:

- **`api`** — FastAPI app served by `uvicorn` workers behind an ALB. Stateless. Reads Postgres, Redis, optionally OpenSearch.
- **`worker`** — Celery worker pool. Performs ingestion, normalization, scoring, indexing.
- **`scheduler`** — Celery beat. Single instance. Schedules periodic ingestion and recompute jobs.
- **`postgres`** — RDS Postgres with PostGIS extension.
- **`redis`** — ElastiCache Redis. DB 0 = Celery, DB 1 = API cache.
- **`opensearch`** — Optional. AWS OpenSearch Service or a single-node container.
- **`frontend`** — Static React build served from S3 + CloudFront, or co-located behind the ALB at `/`.

Data flows in one direction: external → ingestion → Postgres → analysis → API/cache/search → dashboard. No back-edges.

### 4.3 Module boundaries (in-process)

Within the `app/` package:

- `ingestion/` may import from `db/`, `normalization/`, `observability/`, `cache/` (for invalidation hooks).
- `analysis/` may import from `db/`, `observability/`.
- `api/` may import from `db/`, `analysis/`, `search/`, `cache/`, `observability/`.
- `db/` imports nothing from the others.
- `normalization/` imports from `db/` (models only) and `observability/`.

This is enforced by an `import-linter` config in CI. It is the single largest cheap win for a "feels like a real codebase" signal.

---

## 5. Repository Structure

```
civic-access-index/
  README.md
  CHANGELOG.md
  LICENSE
  pyproject.toml              # uv + ruff + mypy + pytest config
  uv.lock
  .python-version
  .pre-commit-config.yaml
  .editorconfig
  .gitignore
  docker-compose.yml
  docker-compose.override.yml.example
  .env.example
  Makefile
  Dockerfile.api
  Dockerfile.worker
  Dockerfile.frontend

  app/
    __init__.py
    main.py                   # FastAPI factory + lifespan
    config.py                 # pydantic-settings, layered env
    logging.py                # structlog setup
    errors.py                 # domain exception hierarchy + handlers
    importlinter.cfg

    api/
      __init__.py
      v1/
        __init__.py           # APIRouter aggregation
        health.py
        tracts.py
        amenities.py
        providers.py
        scores.py
        search.py
        ingestion_runs.py
        admin.py
      dependencies.py         # DI: db session, settings, admin auth
      schemas/                # Pydantic response/request models
        __init__.py
        tract.py
        amenity.py
        provider.py
        score.py
        ingestion.py
        common.py             # pagination, error envelope
      pagination.py           # cursor helpers
      etag.py

    db/
      __init__.py
      session.py              # async engine, session factory
      base.py                 # DeclarativeBase + naming convention
      types.py                # custom column types (geometry helpers)
      models/
        __init__.py
        data_source.py
        ingestion_run.py
        census_tract.py
        amenity.py
        provider.py
        transit_stop.py
        access_metric.py
        access_score.py
        data_quality_issue.py
      migrations/
        env.py
        script.py.mako
        versions/

    ingestion/
      __init__.py
      base.py                 # SourceAdapter protocol + base classes
      pipeline.py             # IngestionPipeline orchestrator
      registry.py             # name → adapter lookup
      context.py              # RunContext dataclass
      snapshots.py            # S3 / local content-addressed store
      rate_limits.py          # token-bucket helpers
      retries.py              # tenacity policies
      validators.py           # shared payload validators
      sources/
        __init__.py
        census_acs.py
        census_tiger.py
        usda_food_access.py
        cms_providers.py
        osm_overpass.py

    normalization/
      __init__.py
      addresses.py            # USPS-style normalization
      categories.py           # OSM/CMS → canonical category mapping
      geospatial.py           # CRS reprojection, point validation
      census.py               # GEOID parsing, ACS variable mapping
      providers.py

    analysis/
      __init__.py
      metrics/
        __init__.py
        registry.py           # @register_metric decorator
        base.py               # TractMetric ABC
        nearest_distance.py
        count_within_radius.py
        demographic.py
        food_access.py
      scoring.py              # subscores + composite formula
      percentiles.py          # statewide / county percentile binning
      explanations.py         # explanation JSON builder

    search/
      __init__.py
      client.py               # OpenSearch client factory
      indexing.py             # bulk index helpers
      mappings.py             # index schemas
      queries.py              # query DSL builders
      aliases.py              # zero-downtime alias rotation

    cache/
      __init__.py
      client.py
      keys.py                 # versioned key builders
      decorators.py           # @cached for endpoint handlers
      invalidation.py

    workers/
      __init__.py
      celery_app.py
      beat_schedule.py
      tasks/
        __init__.py
        ingest.py
        score.py
        index.py
        maintenance.py

    observability/
      __init__.py
      logging_middleware.py
      request_id.py
      metrics.py              # Prometheus / OTel counters & histograms
      health.py

  frontend/
    package.json
    pnpm-lock.yaml
    vite.config.ts
    tsconfig.json
    index.html
    src/
      main.tsx
      App.tsx
      api/
        client.ts
        tracts.ts
        scores.ts
        ingestion.ts
      components/
        MapView.tsx
        ChoroplethLayer.tsx
        FilterPanel.tsx
        TractDetailPanel.tsx
        ScoreBreakdown.tsx
        IngestionStatus.tsx
        DataOpsConsole.tsx
        ErrorBoundary.tsx
      hooks/
        useTractQuery.ts
        useScoreDistribution.ts
      lib/
        format.ts
        colors.ts
      styles/

  infra/
    terraform/
      backend.tf
      versions.tf
      environments/
        dev/
          main.tf
          terraform.tfvars
        prod/
          main.tf
          terraform.tfvars
      modules/
        network/
        ecs_cluster/
        ecs_service/
        rds_postgres/
        elasticache_redis/
        opensearch/
        s3_bucket/
        cloudwatch_dashboard/
        iam_roles/
        secrets/

  scripts/
    bootstrap_dev.py          # one-shot DB init + seed
    run_ingestion.py          # CLI wrapper
    recompute_scores.py
    reindex_search.py
    export_demo_snapshot.py
    check_coverage.py         # lint helper: which sources stale?

  tests/
    conftest.py
    factories/
    unit/
      analysis/
      ingestion/
      normalization/
    integration/
      api/
      db/
      pipeline/
    e2e/
      test_full_pipeline.py

  docs/
    architecture.md
    data_sources.md
    scoring_methodology.md
    api_examples.md
    operations.md
    runbooks/
      ingestion_failure.md
      score_recompute.md
      reindex_search.md
    adr/
      0001-modular-monolith.md
      0002-postgis-over-managed-geo.md
      0003-celery-over-arq.md
      0004-srid-strategy.md
      0005-scoring-transparency.md

  .github/
    workflows/
      ci.yml
      deploy-dev.yml
      deploy-prod.yml
    pull_request_template.md
    CODEOWNERS
```

---

## 6. Data Model

### 6.1 Conventions

- All tables: `id BIGSERIAL PRIMARY KEY`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` with a trigger.
- All foreign keys named `<referent>_id`. All FK constraints named `fk_<table>_<column>`.
- All indexes named `ix_<table>_<columns>`. Unique constraints `uq_<table>_<columns>`.
- All check constraints named `ck_<table>_<rule>`.
- Geometry columns use SRID 4326 (WGS84) for storage. Projected calculations happen in 5070 (NAD83 / Conus Albers Equal Area) for the continental US.
- JSONB columns end in `_json` and have a CHECK that they are objects (not arrays/scalars) unless explicitly noted.
- Soft deletes are not used. Deletions are real and rare; ingestion is the dominant write path.
- Naming convention is enforced via SQLAlchemy `MetaData(naming_convention=...)` so Alembic autogenerate produces consistent constraint names.

### 6.2 Core tables

The original spec is correct in shape. Refinements:

**`data_sources`** — add `slug` (unique, URL-safe, e.g. `census_acs_5y`), `version_string` (the upstream dataset version we're tracking, e.g. `ACS5Y_2023`), and `default_refresh_cron` (cron expression consumed by Celery beat).

**`ingestion_runs`** — add `idempotency_key` (sha256 of source slug + version + run-day) with a unique index, `content_hash` (sha256 of the raw payload bundle, used to detect "no change since last run"), and `triggered_by` (`schedule | manual | api`). Status is an enum: `queued | running | succeeded | partial | failed | skipped_no_change`.

**`census_tracts`** — `geoid` is unique (this is the GEOID11 11-character string). Add a `centroid GEOMETRY(Point, 4326)` column populated by trigger from `geometry`, with a GIST index. Add a generated `geometry_5070 GEOMETRY(MultiPolygon, 5070)` column for distance calculations, also indexed. The duplication is worth it to avoid per-query reprojection.

**`amenities`** and **`providers`** — add `external_id_hash` (sha256 of `source_id + source_record_id`) as a unique index, which becomes the upsert key. Add `geocoded` (boolean) and `geocode_confidence` (enum: `exact | rooftop | parcel | street | postal | derived | none`) for honest provenance.

**`access_metrics`** — partition by `metric_name` if you want to demonstrate awareness, otherwise plain table with `(census_tract_id, metric_name, computed_at DESC)` index. `metric_value` is `DOUBLE PRECISION`. Add `metric_version` (integer; bump when the formula changes).

**`access_scores`** — one row per tract per `score_run` (a foreign key to a new `score_runs` table that records when and with what weights a recompute was performed). This makes weight changes auditable.

**Add `score_runs`** —

```
score_runs
  id
  triggered_by                # schedule | manual | api
  weights_json                # the exact weight vector used
  metrics_version             # snapshot of metric formula versions
  status                      # running | succeeded | failed
  started_at
  completed_at
  error_summary
```

**`data_quality_issues`** — add `dedup_key` (hash over `ingestion_run_id + issue_type + source_record_id`) to prevent the same issue being logged twice on retry. `severity` is an enum.

### 6.3 Indexing strategy

- GIST indexes on every geometry column actually queried (`census_tracts.geometry`, `census_tracts.centroid`, `census_tracts.geometry_5070`, `amenities.location`, `providers.location`).
- BRIN index on `ingestion_runs.started_at` (time-series query pattern, cheap).
- B-tree on `(census_tract_id, metric_name)` for `access_metrics`.
- Partial unique index on `ingestion_runs (data_source_id) WHERE status = 'running'` to enforce "only one running ingestion per source" without a separate lock table.
- Covering indexes (`INCLUDE (...)`) on `access_scores` so the common dashboard query is index-only.

### 6.4 Migrations

Alembic. One migration per logical change. Autogenerate is the starting point; PostGIS columns and trigger functions need hand-edits. Every migration includes a meaningful `downgrade()` even if the project never uses it — it forces you to think about reversibility.

A pre-commit hook (`alembic check`) verifies that the schema matches the latest migration head, catching the most common Alembic footgun.

---

## 7. Ingestion Subsystem

### 7.1 The adapter contract

Every source implements one Protocol. This is the single most important abstraction in the codebase.

```python
from typing import AsyncIterator, Protocol

class SourceAdapter(Protocol):
    slug: str
    display_name: str
    refresh_strategy: RefreshStrategy

    async def discover(self, ctx: RunContext) -> DiscoveryResult:
        """Return a content_hash + manifest of what we'd fetch.
        Used for skip_no_change short-circuit before paying fetch cost."""

    async def fetch(self, ctx: RunContext) -> AsyncIterator[RawRecord]:
        """Yield raw records. Adapter handles pagination, rate limits,
        and writes the raw bundle to ctx.snapshot_writer."""

    def parse(self, raw: RawRecord) -> ParsedRecord:
        """Pure function. Pydantic-validated."""

    def normalize(
        self, parsed: ParsedRecord, ctx: RunContext
    ) -> NormalizationResult:
        """Returns either a CanonicalRecord or a Rejection with reason."""
```

`RefreshStrategy` is `daily | weekly | monthly | on_demand`. `RunContext` carries the `ingestion_run` row, an S3 snapshot writer, a logger bound with `run_id`, and a rate limiter.

### 7.2 The pipeline

`IngestionPipeline.run(adapter, trigger)` is the single entry point. Its job is to make every adapter's life simple:

```
1. Create ingestion_run (status=queued → running)
2. Bind logger with run_id, source_slug
3. Call adapter.discover(); if content_hash matches last successful run,
   short-circuit to status=skipped_no_change. Record decision.
4. Open S3 snapshot writer (content-addressed bucket key:
   s3://bucket/raw/{source_slug}/{run_id}/payload.{ext})
5. Stream adapter.fetch() → snapshot writer + parse buffer
6. For each parsed record: validate, normalize.
   - canonical → buffer for batched upsert
   - rejection → write to data_quality_issues (deduped)
7. Bulk upsert canonical buffer (asyncpg COPY where possible,
   ON CONFLICT for change tracking)
8. Update ingestion_run counts and status.
9. Enqueue downstream tasks: recompute_metrics(tract_ids_touched),
   reindex_search(types_touched).
10. Emit metrics + logs.
```

Critical properties:

- **Idempotent.** Re-running with unchanged upstream is a no-op (saved by step 3).
- **Crash-safe.** Pipeline state lives in `ingestion_runs`, not in worker memory. A killed worker's run becomes recoverable: a maintenance task marks runs with `status=running` older than the configured timeout as `failed` with `error_summary='worker_timeout'`.
- **Observable.** Every transition is logged with structured fields; counts are written incrementally so the dashboard sees live progress.

### 7.3 Rate limits and retries

- `tenacity` for retries with exponential backoff and jitter. Defaults: 5 attempts, 1s → 16s, full jitter.
- A token-bucket rate limiter (`aiolimiter`) per source. Census API caps are generous; OSM Overpass is touchy and gets a slow bucket.
- `httpx.AsyncClient` instances are per-pipeline-run, with HTTP/2 enabled and a 30s default timeout. Connection pool size is conservative (10) to avoid hammering small endpoints.
- Circuit breaker (`purgatory` or hand-rolled) on adapters that have failed N times in a window — the pipeline marks them `failed` with `error_summary='circuit_open'` rather than retrying into the void.

### 7.4 Snapshots

Raw payloads are content-addressed in S3. Local dev uses MinIO or a local filesystem-backed S3-compatible mock. The path is deterministic from `(source_slug, run_id)`, and the `raw_snapshot_uri` column in `ingestion_runs` is the only place the dashboard needs to know.

A nightly maintenance task can prune snapshots older than 30 days for cost; in v1 just keep everything.

### 7.5 Source adapters (v1)

Five adapters, in implementation order:

1. **`census_tiger`** — TIGER/Line shapefiles for Massachusetts census tracts. Static, zipped, large but bounded. Establishes the geographic backbone.
2. **`census_acs`** — ACS 5-year estimates via the Census API. Pulls a curated set of variables (population, median income, poverty rate, vehicle access, age, disability, English proficiency).
3. **`usda_food_access`** — USDA Food Access Research Atlas CSV. Tract-keyed, joins cleanly to TIGER.
4. **`osm_overpass`** — OpenStreetMap amenities (groceries, pharmacies, libraries, clinics, schools, shelters) within a Massachusetts bounding box. Overpass QL queries, rate-limited heavily.
5. **`cms_providers`** — CMS Provider Data Catalog (hospitals, nursing homes, FQHCs). CSV download.

Each adapter is roughly 150–300 lines once the base classes are doing the heavy lifting.

---

## 8. Normalization Subsystem

Normalization is where messy reality becomes a queryable canonical model. Three concerns:

**Address normalization.** Lightweight: lowercase, strip extras, USPS street-suffix mapping (`Street → St`), state-name → state-FIPS lookup. Don't try to be a geocoder. If lat/lng is missing, it's missing — record it as a `data_quality_issue` and continue.

**Category mapping.** OSM uses `amenity=*` and `shop=*`. CMS uses its own type codes. Both map to a small canonical vocabulary (`grocery`, `pharmacy`, `clinic`, `hospital`, `library`, `school`, `shelter`, `urgent_care`, `nursing_home`, `fqhc`). The mapping table lives in code (a single dict in `normalization/categories.py`) for transparency, not in the database.

**Geospatial validation.** Reject `(0, 0)` and other null-island sentinels. Reject points outside the Massachusetts bounding box (with a 50-mile margin for edge cases). Snap coordinates to 6 decimal places to deduplicate. Reject `lat > 90` or `|lng| > 180` outright. Each rejection is a `data_quality_issue` with `issue_type='invalid_geo'`.

**Census GEOID handling.** Parse and validate the 11-character format. Pad state and county FIPS to required widths. The most common bug source — handle it deliberately.

---

## 9. Geospatial Analysis & Scoring

### 9.1 CRS strategy

Storage in 4326 (WGS84). Distance and area calculations in 5070 (Albers Equal Area). For the small radii used here (≤5 miles), 5070 produces accurate enough results that it's not worth the cost of `geography` type math.

The `census_tracts.geometry_5070` generated column is the single biggest perf win — every `ST_Distance` query runs against a pre-projected, indexed geometry.

### 9.2 Metric registry

Metrics are pluggable, declarative, and self-describing.

```python
@register_metric
class NearestGroceryDistanceMiles(TractMetric):
    name = "nearest_grocery_distance_miles"
    unit = "miles"
    direction = MetricDirection.HIGHER_IS_WORSE
    version = 1

    async def compute(self, tract: CensusTract, db: AsyncSession) -> float | None:
        # ST_Distance against amenities of normalized_category='grocery'
        ...

    def interpret(self, value: float, percentile: float) -> str:
        if percentile >= 80:
            return "Longer-than-average distance to grocery access"
        ...
```

The registry pattern means: adding a metric is one file, and the scoring engine, percentile job, explanation builder, and API documentation all pick it up automatically.

Initial metric set:

- `population` (denominator, not scored)
- `poverty_rate`
- `no_vehicle_household_rate`
- `elderly_rate`
- `disability_rate`
- `limited_english_rate`
- `nearest_grocery_distance_miles`
- `nearest_pharmacy_distance_miles`
- `nearest_hospital_distance_miles`
- `nearest_fqhc_distance_miles`
- `groceries_within_1_mile`
- `pharmacies_within_2_miles`
- `clinics_within_2_miles`
- `usda_low_income_low_access_flag` (binary)

### 9.3 Percentiles

Percentiles are computed both statewide and within-county and stored on each metric row. This enables both "worst tracts in MA" and "worst tracts within Suffolk County" views without recomputing on read.

Computation uses Postgres `percent_rank() OVER (PARTITION BY ...)`. For the MA-only v1, this is well under a second on the full table.

### 9.4 Subscores

Each subscore is the mean of its component metric percentiles, with metric direction respected:

```
healthcare_gap_score = mean(
    pct(nearest_hospital_distance_miles),       # higher distance → higher gap
    pct(nearest_fqhc_distance_miles),
    pct(nearest_pharmacy_distance_miles),
    100 - pct(clinics_within_2_miles),          # higher count → lower gap
)

food_gap_score = mean(
    pct(nearest_grocery_distance_miles),
    100 - pct(groceries_within_1_mile),
    100 * usda_low_income_low_access_flag,
)

transit_gap_score = mean(
    pct(no_vehicle_household_rate),             # proxy in v1; refine when GTFS lands
)

socioeconomic_vulnerability_score = mean(
    pct(poverty_rate),
    pct(no_vehicle_household_rate),
    pct(disability_rate),
    pct(elderly_rate),
    pct(limited_english_rate),
)
```

### 9.5 Composite

```
Civic Access Index =
    0.35 * healthcare_gap_score
  + 0.25 * food_gap_score
  + 0.20 * transit_gap_score
  + 0.20 * socioeconomic_vulnerability_score
```

Weights live in `analysis/scoring.py` as a typed `dataclass(frozen=True)` and are echoed back in every API response and in the `score_runs.weights_json` column. Reviewers should never need to ask "what weights produced this?"

### 9.6 Explanations

Every score is accompanied by a structured explanation:

```json
{
  "tract_geoid": "25017383100",
  "score_run_id": 42,
  "weights": {
    "healthcare_gap_score": 0.35,
    "food_gap_score": 0.25,
    "transit_gap_score": 0.20,
    "socioeconomic_vulnerability_score": 0.20
  },
  "composite_score": 82.4,
  "subscores": {
    "healthcare_gap_score": 78.1,
    "food_gap_score": 88.2,
    "transit_gap_score": 91.0,
    "socioeconomic_vulnerability_score": 73.5
  },
  "main_drivers": [
    {
      "metric": "no_vehicle_household_rate",
      "value": 18.2,
      "unit": "percent",
      "percentile_statewide": 91,
      "interpretation": "High proportion of households without vehicle access",
      "source": {
        "slug": "census_acs",
        "ingestion_run_id": 1287,
        "fetched_at": "2026-04-12T03:14:08Z"
      }
    }
  ],
  "limitations": [
    "Amenity data may be incomplete where OpenStreetMap coverage is sparse",
    "Distance calculations use straight-line distance, not travel time or routed networks",
    "Transit access in v1 is proxied by household vehicle availability; GTFS integration is planned"
  ]
}
```

The `limitations` field is the single most important piece of intellectual honesty in the project. It signals public-sector maturity and protects against misuse.

---

## 10. API Layer

### 10.1 Conventions

- Versioned URL prefix: `/api/v1/...`. Health endpoints are unversioned at root.
- JSON over HTTP. No XML, no JSONP.
- Cursor-based pagination. Offset pagination is forbidden (it breaks under concurrent inserts and is slow at scale).
- Every list endpoint returns `{ "data": [...], "page": { "next_cursor": "...", "has_more": true } }`.
- Errors follow RFC 9457 (Problem Details for HTTP APIs):

  ```json
  { "type": "https://docs.example.com/errors/tract-not-found",
    "title": "Tract not found", "status": 404,
    "detail": "No census tract with geoid=99999999999",
    "instance": "/api/v1/tracts/99999999999" }
  ```

- Every endpoint declares a Pydantic response model. There are no untyped responses.
- ETags on cacheable GETs. `If-None-Match` returns `304` from Redis without touching Postgres.
- `Cache-Control` headers reflect the underlying volatility (tracts: `max-age=86400`, ingestion runs: `no-cache`).
- Compression: `gzip` and `br` via the ALB.
- CORS: configured for the dashboard origin only.

### 10.2 Endpoint catalog

The original spec is correct. Refinements:

- `GET /healthz` — process-up. Always 200 if the server can respond.
- `GET /readyz` — checks DB ping, Redis ping, last successful ingestion within SLO. Returns 503 with reasons if not ready.
- `GET /version` — `{ "version": "...", "git_sha": "...", "built_at": "..." }`.
- All `bbox` params are `min_lon,min_lat,max_lon,max_lat` (GeoJSON convention).
- `near=` accepts `lat,lng` or a place name resolved via search.
- Admin endpoints (`POST /api/v1/admin/...`) require an `X-Admin-Token` header. Token is a single shared secret in Secrets Manager. Not user auth — operations auth.

### 10.3 Errors and exception handling

A small domain exception hierarchy in `errors.py`:

```python
class CivicAccessError(Exception): ...
class NotFoundError(CivicAccessError): ...
class ValidationError(CivicAccessError): ...
class IngestionError(CivicAccessError): ...
class ExternalServiceError(CivicAccessError): ...
```

A FastAPI exception handler maps each to an RFC 9457 response. Anything else gets a 500 with a logged traceback and a generic body — never leak stack traces to clients.

### 10.4 Pagination

`Cursor` is an opaque base64-encoded JSON `{"k": ..., "id": ...}` where `k` is the last sort-key value and `id` is the last primary key (tiebreaker). Page size capped at 1000, default 50.

---

## 11. Caching Layer

Three caches, in increasing volatility tolerance:

**HTTP caching (client-side).** ETag + Cache-Control. Free, biggest win.

**Redis caching (server-side).** Only on read-heavy endpoints whose responses are non-trivial to compute. Key format:

```
v{schema_version}:{endpoint_id}:{hash_of_normalized_params}
```

Invalidation by version bump (e.g. on score recompute, increment the global schema_version). This avoids the "delete cache by pattern" trap. A `@cached(...)` decorator wraps endpoint handlers; bypass via `Cache-Control: no-cache` request header for ops debugging.

**In-process caching.** `functools.lru_cache` on truly static lookups (category mappings, weight vectors). Lifetime = process lifetime.

Cache stampede protection: the `@cached` decorator uses `redis.set(nx=True, ex=lock_ttl)` for a singleflight lock; concurrent misses wait briefly rather than all hitting Postgres.

---

## 12. Search Layer (Optional, Feature-Flagged)

OpenSearch is genuinely valuable for a "find everything containing 'pharmacy' near Worcester" query that combines text and geo. It is also the most likely milestone to slip. Therefore:

- Behind a `SEARCH_ENABLED` env var. The system runs cleanly without it.
- Three indices: `tracts`, `amenities`, `providers`. Mappings include geo_point fields, normalized category as keyword, and `name` as text with both `english` analyzer and a `.keyword` subfield.
- Indexing happens via Celery tasks triggered by ingestion completion. Bulk API. Refresh interval relaxed to `30s` on indexing-heavy windows.
- Zero-downtime reindex via alias rotation: write to `amenities_v2`, point alias `amenities` once green, drop `amenities_v1`. The `aliases.py` helper encodes this dance.

If time pressures, this is the first thing to drop. Document the absence honestly.

---

## 13. Frontend

### 13.1 Architecture

A single-page React app, ~6–10 components. Vite for build, TypeScript strict, TanStack Query for data fetching and cache. No Redux or other state library — TanStack Query plus React state suffices.

### 13.2 Pages

Two pages plus a console:

- `/` — Map page. MapLibre vector tiles for base map (free Carto or Protomaps tiles). Choropleth layer for the Civic Access Index. Click a tract → side panel slides in.
- `/tract/:geoid` — Standalone detail page (deep-linkable). Same content as the side panel, but addressable.
- `/ops` — Data Operations console. Tables of data sources, ingestion runs, recent issues. Manual rerun buttons (with confirmation dialogs). Hidden behind a DEV/admin gate; in prod accessible only via VPN or admin token.

### 13.3 Components worth naming

- `MapView` — owns MapLibre instance and view state. Children consume context.
- `ChoroplethLayer` — turns score data into MapLibre paint expressions. Uses fixed quantile breaks computed server-side and fetched once.
- `FilterPanel` — county, score-type, threshold filters. State synced to URL query params for shareable links.
- `TractDetailPanel` — score breakdown, demographic snapshot, nearby amenities list, source provenance. Renders the explanation JSON faithfully.
- `ScoreBreakdown` — pure visual component, takes the explanation JSON as a prop. Donut + driver list.
- `IngestionStatus` — used on `/ops` and as a small banner in dev mode.
- `ErrorBoundary` — catches render errors and falls back gracefully.

### 13.4 Accessibility

Color palette is colorblind-friendly (ColorBrewer `YlOrRd`). All map interactions reachable via keyboard (tract list as a keyboard-navigable secondary view). All form controls labeled. Contrast meets WCAG AA. The `eslint-plugin-jsx-a11y` rules are enabled and CI-enforced.

---

## 14. Workers and Scheduling

### 14.1 Celery topology

- **Default queue**: short tasks (cache warming, search reindex deltas).
- **Ingestion queue**: long-running fetch+normalize. Concurrency=2 in dev, =4 in prod.
- **Analysis queue**: metric and score recomputation.

A single worker process can subscribe to multiple queues; in prod they're separate ECS services for blast-radius isolation.

### 14.2 Beat schedule

- `census_acs` — monthly (first of month, 03:00 UTC).
- `census_tiger` — annually (it's geometry).
- `usda_food_access` — quarterly.
- `osm_overpass` — weekly.
- `cms_providers` — weekly.
- `recompute_scores` — daily, 04:00 UTC, but also auto-triggered by any ingestion that touches metrics.
- `prune_snapshots` — daily.
- `mark_stale_runs_failed` — every 15 minutes.

### 14.3 Task design rules

- Tasks accept primitive arguments (ids, slugs), never SQLAlchemy objects.
- Tasks are idempotent. Re-execution is safe.
- Tasks use `bind=True` and structured logging with `task_id`, `run_id`.
- Long tasks emit progress via Redis (`run_id → percent`) for the dashboard.
- `acks_late=True` and `task_reject_on_worker_lost=True` so a killed worker's task is re-queued, not dropped.

---

## 15. Observability

### 15.1 Logging

`structlog` in JSON mode. Every log line includes:

- `timestamp` (ISO 8601 UTC)
- `level`
- `event` (the message)
- `service` (`api` | `worker` | `scheduler`)
- `request_id` (API) or `task_id` / `run_id` (worker)
- `git_sha`
- contextual fields bound by the caller

A FastAPI middleware mints a `request_id` (or honors an inbound `X-Request-Id`) and binds it to the structlog context for the request's lifetime.

### 15.2 Metrics

Prometheus-style counters and histograms via `prometheus_client`, exposed at `/metrics` (locked to internal networks in prod). Minimum metrics:

- `http_requests_total{method,route,status}`
- `http_request_duration_seconds{method,route}` (histogram)
- `ingestion_run_duration_seconds{source,status}` (histogram)
- `ingestion_records_total{source,outcome}`
- `score_recompute_duration_seconds`
- `cache_hits_total{key_prefix}`, `cache_misses_total{key_prefix}`
- `db_pool_active`, `db_pool_idle`
- `celery_queue_depth{queue}`

In AWS, scrape via CloudWatch agent or skip Prometheus and emit to CloudWatch metrics directly. A CloudWatch dashboard is checked in as Terraform.

### 15.3 Tracing

OpenTelemetry SDK, exporter to console in dev and to AWS X-Ray in prod. Auto-instrumentation for FastAPI, SQLAlchemy, httpx. Manual spans around the ingestion pipeline phases. Optional in v1 if hours run short.

### 15.4 Health

Three endpoints:

- `/healthz` — liveness. Returns 200 if the process is up.
- `/readyz` — readiness. Returns 200 only if DB and Redis pings succeed within 1s.
- `/version` — build identification.

Plus an internal `/health/detail` (admin-token gated) that surfaces last successful ingestion per source, queue depths, and cache hit rates.

---

## 16. Security

This is a public-read data platform with admin-controlled writes. Threat model is correspondingly narrow.

**Public surface.** All `GET /api/v1/...` endpoints are unauthenticated, read-only, rate-limited (per-IP, 60 rpm default via Redis token bucket). No user data is ever returned.

**Admin surface.** `POST /api/v1/admin/...` requires `X-Admin-Token`. Token is a long random string in AWS Secrets Manager, loaded via `pydantic-settings`. In prod the admin endpoints are also IP-restricted via ALB rules to the operator's allowlist.

**Database.** No raw SQL strings concatenated with user input — SQLAlchemy parameterized queries everywhere. The least-privilege RDS user for the API only has `SELECT, INSERT, UPDATE` on canonical tables; the worker user adds `DELETE` on `data_quality_issues` and DDL on nothing.

**Secrets.** Never in repo. Never in logs (structlog has a redaction processor for any field whose key matches `*token*|*secret*|*password*|*key*`). `.env.example` documents the required variables; real `.env` is gitignored.

**Dependencies.** `uv lock` for reproducibility. CI runs `pip-audit` (or `uv pip audit` once stable) and fails on high-severity advisories. Renovate or Dependabot opens weekly PRs.

**HTTP headers.** `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy` set on the dashboard.

**Input validation.** Pydantic on every request body. Bbox coordinates bounds-checked. Geoids regex-validated. SQL-parameter type-checked by SQLAlchemy. Path traversal not a concern (no file operations on user input).

---

## 17. Configuration Management

`pydantic-settings` with environment variables. Settings class is a frozen `BaseSettings` with explicit fields and types. Layered loading order:

1. Defaults declared in the class.
2. `.env` (dev only).
3. Environment variables (always wins).
4. AWS Secrets Manager values are *injected as env vars* by ECS task definition; the app does not call AWS directly. This keeps the app cloud-agnostic and locally runnable.

Twelve-factor compliant. Settings is a singleton accessed via FastAPI dependency injection or a module-level `get_settings()` (cached).

```python
class Settings(BaseSettings):
    environment: Literal["dev", "staging", "prod"]
    database_url: PostgresDsn
    redis_url: RedisDsn
    s3_bucket: str
    opensearch_url: HttpUrl | None = None
    search_enabled: bool = False
    admin_token: SecretStr
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    git_sha: str = "unknown"
    # ... etc
```

---

## 18. Testing Strategy

**Pyramid, not ice cream cone.**

- **Unit tests.** Pure functions in `analysis/`, `normalization/`, `ingestion/parsers`. Fast, no IO. Run on every save in dev. Target: most logic lives here.
- **Integration tests.** Real Postgres (via `pytest-postgresql` with PostGIS), real Redis (via `fakeredis` or testcontainers). Cover: ingestion pipeline end-to-end against fixture payloads, API endpoints with seeded data, score computation against known inputs.
- **End-to-end tests.** A single test that runs `bootstrap_dev`, ingests one fixture source, recomputes scores, hits a couple of endpoints, asserts shape. This is the smoke test that proves the whole system works.

**Coverage target.** 80% line coverage on `app/`, with an explicit waiver list (e.g. `main.py` lifespan hooks). Coverage is reported in CI but not gated above 80% — preventing regression matters more than chasing 95%.

**Fixtures.** `polyfactory` for Pydantic model factories. Real fixture payloads (small snippets of actual Census/USDA/OSM responses) committed under `tests/fixtures/`. Mock external HTTP via `respx`.

**Test data.** A seed dataset (5 census tracts, ~50 amenities, ~20 providers) ships in `scripts/load_local_seed_data.py` for development without paying ingestion costs.

**Property-based testing.** `hypothesis` for: percentile computation invariants (always 0–100, monotonic), GEOID parser (round-trip), category mapper (idempotent on already-canonical input). Worth the small investment; high signal.

---

## 19. Code Quality and Tooling

- **`ruff`** as both linter and formatter, configured in `pyproject.toml`. Rule set: `ALL` minus deliberate exclusions (e.g., `D` docstring style relaxed for tests).
- **`mypy --strict`** on `app/`. Tests get `mypy` without `--strict`.
- **`import-linter`** to enforce module boundaries from §4.3.
- **`pre-commit`** runs ruff, mypy on changed files, alembic check, and a "no `print()` left behind" custom hook.
- **`commitizen`** for conventional-commit messages (optional, but enables auto-generated CHANGELOG).
- **`Makefile`** as the user interface for common tasks: `make dev`, `make test`, `make lint`, `make migrate`, `make seed`, `make ingest SRC=osm_overpass`, `make recompute`.

---

## 20. CI/CD

### 20.1 Pipelines

- **`ci.yml`** — runs on every PR and push to `main`:
  1. `ruff check && ruff format --check`
  2. `mypy app/`
  3. `import-linter`
  4. `pytest tests/unit tests/integration` (with Postgres + Redis service containers)
  5. `pytest tests/e2e` (only on `main` push, not PRs)
  6. `alembic upgrade head` against fresh DB then `alembic check`
  7. Frontend: `pnpm install && pnpm typecheck && pnpm lint && pnpm test`
  8. Build Docker images, scan with `trivy`, push to ECR (only on `main`).

- **`deploy-dev.yml`** — auto-deploys `main` to dev:
  1. `terraform plan -out=plan` against dev workspace.
  2. `terraform apply plan`.
  3. Update ECS services with new image tag.
  4. Run migrations as a one-off ECS task (idempotent).
  5. Smoke-test against `/readyz`.

- **`deploy-prod.yml`** — manual dispatch only. Same shape as dev but requires approval.

### 20.2 Branch policy

- `main` is protected: PRs only, CI required, one approver if collaborators exist.
- Conventional commits → auto-generated CHANGELOG via `commitizen`.
- No force-pushes to `main`.

### 20.3 Migrations in deploys

Migrations run as a pre-deploy ECS task, not in the API container's startup. Two reasons: avoids racing-pods migrating simultaneously, and a failed migration doesn't loop a healthy service into crash-loop.

---

## 21. Infrastructure (Terraform)

### 21.1 Layout

State in S3 with a DynamoDB lock table. One root module per environment (`environments/dev`, `environments/prod`). Shared modules in `modules/`.

### 21.2 Module list

- **`network`** — VPC, public/private subnets in 2 AZs, NAT gateway (single, for cost), security groups.
- **`ecs_cluster`** — Fargate cluster, capacity providers, execution role.
- **`ecs_service`** — generic, parameterized; instantiated three times (api, worker, scheduler).
- **`rds_postgres`** — Postgres 16 with PostGIS extension enabled via parameter group, single AZ in dev, multi-AZ in prod (or a single small instance with snapshot backups in prod-as-portfolio-demo to control cost).
- **`elasticache_redis`** — single-node Redis 7.
- **`opensearch`** — single-node, conditional (`count = var.search_enabled ? 1 : 0`).
- **`s3_bucket`** — for raw snapshots and frontend static assets. Versioning + lifecycle policy.
- **`cloudwatch_dashboard`** — pre-built dashboard with the metrics from §15.2.
- **`iam_roles`** — task roles with least-privilege, separate roles per service.
- **`secrets`** — Secrets Manager entries for the admin token, DB password, etc.

### 21.3 Cost-awareness

The full prod stack should run on one t4g.medium RDS, one cache.t4g.micro Redis, two Fargate services at 0.25 vCPU / 0.5 GB each, and a tiny OpenSearch (or none). Estimated $60–120/month. The Terraform variables expose all sizes so a reviewer can see the dial.

### 21.4 What's deliberately not in Terraform

ACM certificates, Route 53 zones, GitHub OIDC trust — these are one-time per-account setup. Documented in `docs/operations.md` as manual prerequisites.

---

## 22. Local Development Workflow

```
git clone ...
cp .env.example .env
make dev          # docker compose up; waits for healthchecks
make migrate      # alembic upgrade head
make seed         # loads fixture tracts/amenities
make ingest SRC=osm_overpass  # runs one source against live API
make recompute    # recomputes scores
open http://localhost:5173
```

`docker-compose.yml` services: `api`, `worker`, `scheduler`, `postgres`, `redis`, `opensearch` (profile: `search`), `frontend`, `minio` (S3-compatible). Volumes mounted for hot-reload on `app/` and `frontend/src/`. Postgres data in a named volume so it survives `down`.

`docker-compose.override.yml.example` is checked in for power-user tweaks (mounting a local OSM PBF, swapping ports).

---

## 23. Documentation

Three audiences, three flavors:

**`README.md`** — front door. Opens with the framing paragraph (this is operational infrastructure, not policy advice). One-screen architecture diagram. Quickstart in five commands. Pointers into `docs/`.

**`docs/`** — for someone evaluating or extending the system:
- `architecture.md` — fuller version of §4 with ADR back-references.
- `data_sources.md` — table of sources with refresh cadence, row counts, license.
- `scoring_methodology.md` — the math, the weights, the limitations, citations to comparable indices (CDC SVI, Justice40 CEJST).
- `api_examples.md` — curl recipes for the common endpoints with sample responses.
- `operations.md` — how to deploy, how to bootstrap an AWS account, how to roll back.
- `runbooks/` — playbooks for "ingestion is failing," "scores look wrong," "search index drifted."

**`docs/adr/`** — Architecture Decision Records. Each is one page in the [Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). Initial set is short and specific; the discipline matters more than the volume.

Inline docstrings on every public function in `app/`. Internal helpers can be self-documenting. No verbose docstrings on Pydantic models — the field declarations are the documentation.

---

## 24. Implementation Plan with Hour Budgets

The original spec's seven milestones are correct. Honest estimates:

| # | Milestone | Hours | Notes |
|---|---|---|---|
| 0 | Repo bootstrap | 4 | `pyproject.toml`, ruff, mypy, pre-commit, Makefile, `.env.example`, `.editorconfig`, `LICENSE`, README skeleton, GitHub repo + branch protection. |
| 1 | Platform foundation | 12 | FastAPI app factory, config, structlog, Postgres + Alembic, Celery worker, Redis, `/healthz`, `/readyz`, `/version`, `data_sources` and `ingestion_runs` tables, base classes for `SourceAdapter` and `IngestionPipeline`, docker-compose, Makefile targets. |
| 2 | Census tract base layer | 10 | TIGER ingestion (Massachusetts only), ACS ingestion (curated variables), `census_tracts` table with PostGIS columns, generated `geometry_5070`, GIST indexes, basic `/api/v1/tracts` and `/api/v1/tracts/{geoid}`. |
| 3 | Amenities and providers | 18 | OSM Overpass adapter (this is the time sink — Overpass quirks, category mapping, geo validation), CMS adapter, `amenities` and `providers` tables, normalization, `data_quality_issues` logging, basic listing endpoints. |
| 4 | Metric computation | 14 | Metric registry, the dozen v1 metrics, percentile computation (statewide + county), `access_metrics` table, `recompute_metrics` Celery task. |
| 5 | Scoring and explanations | 10 | `score_runs` and `access_scores` tables, scoring formula, `recompute_scores` task, explanation builder, `/api/v1/scores/...` and `/api/v1/tracts/{geoid}/explanation`. |
| 6 | Frontend dashboard | 18 | Vite + React scaffold, MapLibre choropleth, FilterPanel, TractDetailPanel with explanation rendering, `/ops` console, deep-linkable tract URLs. |
| 7 | Caching | 6 | Redis client, `@cached` decorator, key versioning, ETags on stable endpoints, cache stampede protection. |
| 8 | Search (optional) | 8 | OpenSearch indexing tasks, three index mappings, `/api/v1/search`, alias rotation. Behind feature flag — if hours are short, ship dark and document. |
| 9 | Infrastructure | 12 | Terraform modules, dev environment apply, ECR, RDS, Redis, S3, ALB, security groups, secrets. |
| 10 | CI/CD | 6 | Three GitHub Actions workflows, OIDC trust, branch protection, artifact pushing, smoke tests. |
| 11 | Observability polish | 4 | Prometheus metrics, CloudWatch dashboard, log redaction, request_id middleware. |
| 12 | Documentation | 8 | README, architecture diagram, scoring methodology with citations, runbooks, ADRs, API examples. |
| 13 | Testing | covered above | Tests are written *with* each milestone, not as a separate phase. Budget allocation is in each milestone's hours. |
| 14 | Buffer / polish / fixes | 10 | The known-unknowns budget. |
| | **Total** | **140** | |

This is honestly 140, not 120. The 20-hour overrun is real and worth naming. Three ways to land at 120:

1. **Drop OpenSearch** (saves 8h). Document its absence as deliberate.
2. **Drop the `/ops` console**, surface ingestion status as a banner only (saves ~4h).
3. **Trim metrics to 8 instead of 13** (saves ~3h).

A defensible 120-hour scope: M0–M7, M9–M12 with search dropped, ops surfaced minimally. This still lands every "production-shaped" signal.

---

## 25. Definition of Done

A realized v1 satisfies all of:

- [ ] `git clone` + `cp .env.example .env` + `make dev` brings up the full stack on a clean machine.
- [ ] `make migrate && make seed` produces a queryable database in under 60 seconds.
- [ ] At least three public sources ingest end-to-end via `make ingest SRC=...`, with visible runs in the dashboard.
- [ ] Every ingestion run records counts, status, raw snapshot URI, and any rejected rows in `data_quality_issues`.
- [ ] Re-running an unchanged source short-circuits with `status=skipped_no_change`.
- [ ] Scores recompute via `make recompute` and via the admin API.
- [ ] OpenAPI docs at `/docs` are accurate and complete.
- [ ] Dashboard map renders the Civic Access Index choropleth for Massachusetts and the side panel shows a real explanation object.
- [ ] Redis caching is exercised on at least the tract list and score distribution endpoints, with ETag support.
- [ ] (Optional) OpenSearch backs `/api/v1/search` for tracts, amenities, and providers.
- [ ] `terraform apply` against a fresh AWS dev environment succeeds and yields a working deployment.
- [ ] GitHub Actions runs the full test suite on every PR; main-branch pushes deploy to dev automatically.
- [ ] README, scoring methodology, and operations runbooks are written and accurate.
- [ ] CHANGELOG records the v1.0.0 release.
- [ ] At least 5 ADRs document the consequential architectural choices.
- [ ] `mypy --strict` passes on `app/`. `ruff check` passes. Test coverage ≥ 80%.

---

## 26. Risks and Mitigations

**OpenStreetMap Overpass time-outs.** OSM coverage and Overpass uptime are real variables. Mitigation: fixture-backed offline mode for development, retries with long backoff, fall back to Geofabrik PBF + `osmium` for bulk ingest if Overpass fails twice in a row.

**ACS variable churn.** Census variable codes change between vintages. Mitigation: pin the vintage explicitly in the adapter, and the `metric_version` column means a vintage bump is a tracked event, not an invisible drift.

**PostGIS performance on dense queries.** ST_Distance against 50k amenities for every tract can be slow. Mitigation: pre-projected `geometry_5070`, GIST indexes, KNN operators (`<->`) for "nearest" queries. Materialized views for the heaviest joins if measurements warrant.

**Time pressure.** 120 hours is tight. Mitigation: explicit drop-list in §24, and a "first cuttable" ordering — search first, ops console second, marginal metrics third.

**Cost surprises in AWS.** NAT gateway is the silent killer. Mitigation: single NAT in dev, document the option of an instance NAT for further savings, set a billing alarm at $50/month.

**Scope creep on scoring.** "Should we add this metric?" is endless. Mitigation: the v1 metric list is closed; new metrics go to v2. The scoring methodology doc names what is *not* measured to defuse the question.

**Geocoding rabbit hole.** Refusing to build a geocoder is a real engineering choice. Mitigation: state it in the README. CMS data ships with lat/lng; OSM ships with lat/lng; ACS is tract-keyed. v1 does not need a geocoder.

---

## 27. Out of Scope (Explicit v2 Backlog)

To make the cut clear:

- **GTFS transit ingestion** with proper service-frequency analysis. Worth doing later; deceptively time-consuming because each agency's feed is slightly different.
- **FCC broadband data**. Politically and substantively interesting, but the dataset is fiddly and adds little to the architectural story v1 already tells.
- **Multi-state expansion**. Massachusetts only in v1. Adding states is a configuration change, not an architecture change.
- **Historical time-series scoring**. v1 stores the latest score. Bi-temporal scoring (as-of date + ingestion-vintage) is a v2 schema change.
- **Travel-time isochrones** via OSRM or Valhalla. Straight-line distance is honest if the limitations are stated.
- **End-user authentication and saved views**. Operators only.
- **Public hosting under a domain with SLA**. Portfolio demo runs in dev environment; a permanent prod is not required.

---

## 28. Glossary

- **ACS** — American Community Survey, the Census Bureau's annual demographic survey.
- **CMS** — Centers for Medicare & Medicaid Services. Publishes provider data.
- **FQHC** — Federally Qualified Health Center.
- **GEOID** — A standardized geographic identifier (11 chars at the tract level).
- **OSM** — OpenStreetMap.
- **TIGER/Line** — Census Bureau's geographic feature shapefiles.
- **USDA Food Access Atlas** — USDA's tract-level food-access dataset.
- **SRID** — Spatial Reference Identifier; an integer naming a coordinate reference system. 4326 = WGS84 (lat/lng), 5070 = NAD83 / Conus Albers Equal Area.
- **PostGIS** — PostgreSQL's geospatial extension.
- **ADR** — Architecture Decision Record.
- **RFC 9457** — IETF standard for HTTP error response bodies (Problem Details).

---

## 29. References and Comparable Work

The scoring methodology should cite, in `docs/scoring_methodology.md`:

- CDC's Social Vulnerability Index (SVI) — methodologically adjacent.
- USDA Food Access Research Atlas — directly used as a metric input.
- Justice40 CEJST — methodologically adjacent, weights publicly documented.
- Census Bureau ACS variable definitions.

These citations matter. They locate the work in a tradition rather than presenting it as invention.
