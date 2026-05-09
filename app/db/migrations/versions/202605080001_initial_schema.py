"""Initial civic access schema.

Revision ID: 202605080001
Revises:
Create Date: 2026-05-08
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605080001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "data_sources",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("homepage_url", sa.Text(), nullable=True),
        sa.Column("api_url", sa.Text(), nullable=True),
        sa.Column("license", sa.String(length=200), nullable=True),
        sa.Column("refresh_strategy", sa.String(length=120), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_data_sources_name", "data_sources", ["name"])

    op.create_table(
        "census_tracts",
        sa.Column("geoid", sa.String(length=20), nullable=False),
        sa.Column("state_fips", sa.String(length=2), nullable=False),
        sa.Column("county_fips", sa.String(length=3), nullable=False),
        sa.Column("tract_code", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("median_income", sa.Integer(), nullable=True),
        sa.Column("poverty_rate", sa.Float(), nullable=True),
        sa.Column("no_vehicle_household_rate", sa.Float(), nullable=True),
        sa.Column("elderly_rate", sa.Float(), nullable=True),
        sa.Column("disability_rate", sa.Float(), nullable=True),
        sa.Column("limited_english_rate", sa.Float(), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column(
            "centroid",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column("properties_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("geoid"),
    )
    op.create_index("ix_census_tracts_county_fips", "census_tracts", ["county_fips"])
    op.create_index("ix_census_tracts_geoid", "census_tracts", ["geoid"])
    op.create_index("ix_census_tracts_state_fips", "census_tracts", ["state_fips"])

    op.create_table(
        "ingestion_runs",
        sa.Column("data_source_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_seen", sa.Integer(), nullable=False),
        sa.Column("records_created", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_rejected", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("raw_snapshot_uri", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_runs_data_source_id", "ingestion_runs", ["data_source_id"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])

    op.create_table(
        "amenities",
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("source_record_id", sa.String(length=200), nullable=True),
        sa.Column("name", sa.String(length=240), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("normalized_category", sa.String(length=80), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_amenities_category", "amenities", ["category"])
    op.create_index("ix_amenities_normalized_category", "amenities", ["normalized_category"])
    op.create_index("ix_amenities_source_id", "amenities", ["source_id"])
    op.create_index("ix_amenities_source_record_id", "amenities", ["source_record_id"])
    op.create_index("ix_amenities_state", "amenities", ["state"])

    op.create_table(
        "providers",
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("source_record_id", sa.String(length=200), nullable=True),
        sa.Column("name", sa.String(length=240), nullable=True),
        sa.Column("provider_type", sa.String(length=80), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column("cms_rating", sa.Float(), nullable=True),
        sa.Column("accepts_medicare", sa.Boolean(), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_providers_provider_type", "providers", ["provider_type"])
    op.create_index("ix_providers_source_id", "providers", ["source_id"])
    op.create_index("ix_providers_source_record_id", "providers", ["source_record_id"])
    op.create_index("ix_providers_state", "providers", ["state"])

    op.create_table(
        "transit_stops",
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("stop_id", sa.String(length=200), nullable=False),
        sa.Column("agency", sa.String(length=160), nullable=True),
        sa.Column("name", sa.String(length=240), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column("route_count", sa.Integer(), nullable=True),
        sa.Column("service_frequency_score", sa.Float(), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transit_stops_agency", "transit_stops", ["agency"])
    op.create_index("ix_transit_stops_source_id", "transit_stops", ["source_id"])
    op.create_index("ix_transit_stops_stop_id", "transit_stops", ["stop_id"])

    op.create_table(
        "access_metrics",
        sa.Column("census_tract_id", sa.String(), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("metric_unit", sa.String(length=80), nullable=True),
        sa.Column("percentile_statewide", sa.Float(), nullable=True),
        sa.Column("percentile_county", sa.Float(), nullable=True),
        sa.Column("source_run_ids", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["census_tract_id"], ["census_tracts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_metrics_census_tract_id", "access_metrics", ["census_tract_id"])
    op.create_index("ix_access_metrics_metric_name", "access_metrics", ["metric_name"])

    op.create_table(
        "access_scores",
        sa.Column("census_tract_id", sa.String(), nullable=False),
        sa.Column("food_access_score", sa.Float(), nullable=True),
        sa.Column("healthcare_access_score", sa.Float(), nullable=True),
        sa.Column("transit_access_score", sa.Float(), nullable=True),
        sa.Column("digital_access_score", sa.Float(), nullable=True),
        sa.Column("civic_access_index", sa.Float(), nullable=True),
        sa.Column("vulnerability_score", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("explanation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["census_tract_id"], ["census_tracts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("census_tract_id"),
    )
    op.create_index("ix_access_scores_census_tract_id", "access_scores", ["census_tract_id"])
    op.create_index("ix_access_scores_civic_access_index", "access_scores", ["civic_access_index"])
    op.create_index("ix_access_scores_composite_score", "access_scores", ["composite_score"])

    op.create_table(
        "data_quality_issues",
        sa.Column("ingestion_run_id", sa.String(), nullable=True),
        sa.Column("source_record_id", sa.String(length=200), nullable=True),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("issue_type", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_quality_issues_ingestion_run_id", "data_quality_issues", ["ingestion_run_id"])
    op.create_index("ix_data_quality_issues_issue_type", "data_quality_issues", ["issue_type"])
    op.create_index("ix_data_quality_issues_severity", "data_quality_issues", ["severity"])
    op.create_index("ix_data_quality_issues_source_record_id", "data_quality_issues", ["source_record_id"])


def downgrade() -> None:
    op.drop_index("ix_data_quality_issues_source_record_id", table_name="data_quality_issues")
    op.drop_index("ix_data_quality_issues_severity", table_name="data_quality_issues")
    op.drop_index("ix_data_quality_issues_issue_type", table_name="data_quality_issues")
    op.drop_index("ix_data_quality_issues_ingestion_run_id", table_name="data_quality_issues")
    op.drop_table("data_quality_issues")
    op.drop_index("ix_access_scores_composite_score", table_name="access_scores")
    op.drop_index("ix_access_scores_civic_access_index", table_name="access_scores")
    op.drop_index("ix_access_scores_census_tract_id", table_name="access_scores")
    op.drop_table("access_scores")
    op.drop_index("ix_access_metrics_metric_name", table_name="access_metrics")
    op.drop_index("ix_access_metrics_census_tract_id", table_name="access_metrics")
    op.drop_table("access_metrics")
    op.drop_index("ix_transit_stops_stop_id", table_name="transit_stops")
    op.drop_index("ix_transit_stops_source_id", table_name="transit_stops")
    op.drop_index("ix_transit_stops_agency", table_name="transit_stops")
    op.drop_table("transit_stops")
    op.drop_index("ix_providers_state", table_name="providers")
    op.drop_index("ix_providers_source_record_id", table_name="providers")
    op.drop_index("ix_providers_source_id", table_name="providers")
    op.drop_index("ix_providers_provider_type", table_name="providers")
    op.drop_table("providers")
    op.drop_index("ix_amenities_state", table_name="amenities")
    op.drop_index("ix_amenities_source_record_id", table_name="amenities")
    op.drop_index("ix_amenities_source_id", table_name="amenities")
    op.drop_index("ix_amenities_normalized_category", table_name="amenities")
    op.drop_index("ix_amenities_category", table_name="amenities")
    op.drop_table("amenities")
    op.drop_index("ix_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_data_source_id", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_index("ix_census_tracts_state_fips", table_name="census_tracts")
    op.drop_index("ix_census_tracts_geoid", table_name="census_tracts")
    op.drop_index("ix_census_tracts_county_fips", table_name="census_tracts")
    op.drop_table("census_tracts")
    op.drop_index("ix_data_sources_name", table_name="data_sources")
    op.drop_table("data_sources")

