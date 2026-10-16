from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from pipeline.analysis.runner import build_analysis
from pipeline.config import Settings
from pipeline.ingest.runner import ingest_all
from pipeline.model.runner import build_model
from pipeline.transform.runner import transform_all

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def modeled_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    database_path = tmp_path_factory.mktemp("modeled-database") / "flint-modeled.duckdb"
    settings = Settings.from_root(PROJECT_ROOT, database_path)
    ingest_all(settings)
    transform_all(settings)
    build_model(settings)
    return settings


@pytest.fixture(scope="session")
def analysis_settings(modeled_settings: Settings) -> Settings:
    with duckdb.connect(str(modeled_settings.database_path)) as connection:
        connection.execute(
            """
            CREATE OR REPLACE TABLE fact_correspondence_event_current (
                correspondence_event_key VARCHAR,
                doc_id VARCHAR,
                doc_type VARCHAR,
                event_index INTEGER,
                job_key VARCHAR,
                job_id VARCHAR,
                subcontractor_key VARCHAR,
                subcontractor_id VARCHAR,
                scope VARCHAR,
                event_type VARCHAR,
                amount DECIMAL(18, 2),
                financial_impact_type VARCHAR,
                amount_status VARCHAR,
                booking_status VARCHAR,
                schedule_impact_days INTEGER,
                schedule_impact_type VARCHAR,
                approval_status VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO fact_correspondence_event_current VALUES
                ('CO-1:1', 'CO-1', 'CO', 1, 'B2100', 'B2100', 'SUB012', 'SUB012',
                 'excavation', 'change_order', 100, 'cost', 'estimated', 'not_booked',
                 5, 'delay', 'authorized'),
                ('CO-2:1', 'CO-2', 'CO', 1, 'B2100', 'B2100', 'SUB012', 'SUB012',
                 'earthwork', 'change_order', 40, 'contract_value', 'quoted', 'not_booked',
                 NULL, 'unknown', 'proposed'),
                ('CO-3:1', 'CO-3', 'CO', 1, 'C2134', 'C2134', 'SUB012', 'SUB012',
                 'Acceleration of earthwork', 'change_order', 200, 'cost', 'estimated',
                 'unknown', 10, 'recovery', 'pending'),
                ('RFI-1:1', 'RFI-1', 'RFI', 1, 'B2100', 'B2100', 'SUB012', 'SUB012',
                 'utilities', 'potential_cost', 300, 'cost', 'estimated', 'not_booked',
                 NULL, 'unknown', 'unknown'),
                ('LOG-1:1', 'LOG-1', 'LOG', 1, 'B2100', 'B2100', 'SUB012', 'SUB012',
                 NULL, 'backcharge', NULL, 'unknown', 'unknown', 'unknown',
                 NULL, 'unknown', 'disputed')
            """
        )
        connection.execute(
            "ALTER TABLE fact_correspondence_event_current ADD COLUMN evidence_text VARCHAR"
        )
        connection.execute(
            "UPDATE fact_correspondence_event_current "
            "SET evidence_text = 'Synthetic fixture evidence'"
        )
        # API tests use a small synthetic correspondence fact instead of running
        # the external extraction provider, so provide its reconciliation gate.
        connection.execute(
            """
            CREATE OR REPLACE TABLE model_correspondence_reconciliation AS
            SELECT 'synthetic_correspondence_fixture' AS check_name, true AS passed
            """
        )
    build_analysis(modeled_settings)
    return modeled_settings
