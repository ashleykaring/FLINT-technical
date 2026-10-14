from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from pipeline.ai.job_qa import (
    JobQuestionConfigurationError,
    JobQuestionError,
    answer_job_question,
)
from pipeline.api.repository import (
    DashboardDataError,
    JobNotFoundError,
    load_equipment_dashboard,
    load_job_detail,
    load_portfolio_dashboard,
    load_portfolio_insights,
)
from pipeline.api.schemas import (
    DashboardFilters,
    EquipmentDashboard,
    EquipmentFilters,
    JobDetail,
    JobQuestionRequest,
    JobQuestionResponse,
    PortfolioDashboard,
    PortfolioInsights,
)
from pipeline.config import Settings

JobAnswerer = Callable[[JobDetail, EquipmentDashboard, str], JobQuestionResponse]


def create_app(
    settings: Settings | None = None,
    job_answerer: JobAnswerer | None = None,
) -> FastAPI:
    project_settings = settings or Settings.from_root()
    selected_job_answerer = job_answerer or answer_job_question
    app = FastAPI(
        title="FLINT Portfolio API",
        version="0.1.0",
        description="Read-only API over the governed DuckDB analytical marts.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
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

    @app.get("/api/jobs/{job_id}", response_model=JobDetail)
    def job_detail(job_id: str) -> JobDetail:
        try:
            return load_job_detail(project_settings, job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DashboardDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/ask", response_model=JobQuestionResponse)
    def ask_job(job_id: str, request: JobQuestionRequest) -> JobQuestionResponse:
        try:
            detail = load_job_detail(project_settings, job_id)
            equipment = load_equipment_dashboard(
                project_settings,
                EquipmentFilters(job_id=detail.summary.job_id),
            )
            return selected_job_answerer(detail, equipment, request.question.strip())
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except JobQuestionConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except JobQuestionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except DashboardDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/insights", response_model=PortfolioInsights)
    def insights() -> PortfolioInsights:
        try:
            return load_portfolio_insights(project_settings)
        except DashboardDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/equipment", response_model=EquipmentDashboard)
    def equipment(
        division: str | None = Query(default=None),
        ownership: str | None = Query(default=None),
        equipment_type: str | None = Query(default=None),
        job_id: str | None = Query(default=None),
    ) -> EquipmentDashboard:
        try:
            return load_equipment_dashboard(
                project_settings,
                EquipmentFilters(
                    division=division,
                    ownership=ownership,
                    equipment_type=equipment_type,
                    job_id=job_id,
                ),
            )
        except DashboardDataError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return app


app = create_app()
