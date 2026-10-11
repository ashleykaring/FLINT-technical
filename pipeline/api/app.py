from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from pipeline.api.repository import DashboardDataError, load_portfolio_dashboard
from pipeline.api.schemas import DashboardFilters, PortfolioDashboard
from pipeline.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    project_settings = settings or Settings.from_root()
    app = FastAPI(
        title="FLINT Portfolio API",
        version="0.1.0",
        description="Read-only API over the governed DuckDB analytical marts.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/portfolio", response_model=PortfolioDashboard)
    def portfolio(
        division: str | None = Query(default=None),
        contract_type: str | None = Query(default=None),
        project_manager_id: str | None = Query(default=None),
        progress_status: str | None = Query(default=None),
    ) -> PortfolioDashboard:
        try:
            return load_portfolio_dashboard(
                project_settings,
                DashboardFilters(
                    division=division,
                    contract_type=contract_type,
                    project_manager_id=project_manager_id,
                    progress_status=progress_status,
                ),
            )
        except DashboardDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return app


app = create_app()
