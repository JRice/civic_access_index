# Architecture

Civic Access Index starts as a modular monolith with a worker pool. The API, ingestion
adapters, normalization code, geospatial analysis, search indexing, and observability
helpers live in one repository and share one database schema.

The deployment shape still mirrors a production data platform:

- FastAPI serves REST endpoints and OpenAPI documentation.
- Celery workers handle ingestion, normalization, scoring, and indexing.
- PostgreSQL with PostGIS stores normalized geographies and access metrics.
- Redis backs Celery and caches expensive API queries.
- OpenSearch is available for optional text and faceted search.
- Terraform will provision ECS/Fargate, RDS Postgres, ElastiCache, S3, OpenSearch,
  and CloudWatch resources.

Ingestion runs are first-class records. Every public-source fetch should create a run,
store a raw snapshot URI, track counts, preserve failure state, and write data-quality
issues for rejected records.

