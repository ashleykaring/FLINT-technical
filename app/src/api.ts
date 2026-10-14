import type {
  ActiveFilters,
  EquipmentActiveFilters,
  EquipmentDashboard,
  JobDetail,
  JobQuestionResponse,
  PortfolioDashboard,
  PortfolioInsights,
} from "./types";

async function responseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Dashboard API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchPortfolio(filters: ActiveFilters): Promise<PortfolioDashboard> {
  const params = new URLSearchParams();
  if (filters.division) params.set("division", filters.division);
  if (filters.contractType) params.set("contract_type", filters.contractType);
  if (filters.projectManager) params.set("project_manager_id", filters.projectManager);
  if (filters.progressStatus) params.set("progress_status", filters.progressStatus);

  const query = params.size ? `?${params.toString()}` : "";
  const response = await fetch(`/api/portfolio${query}`);
  return responseJson<PortfolioDashboard>(response);
}

export async function fetchJobDetail(jobId: string): Promise<JobDetail> {
  const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
  return responseJson<JobDetail>(response);
}

export async function askJob(
  jobId: string,
  question: string,
): Promise<JobQuestionResponse> {
  const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return responseJson<JobQuestionResponse>(response);
}

export async function fetchPortfolioInsights(): Promise<PortfolioInsights> {
  const response = await fetch("/api/insights");
  return responseJson<PortfolioInsights>(response);
}

export async function fetchEquipment(
  filters: EquipmentActiveFilters,
): Promise<EquipmentDashboard> {
  const params = new URLSearchParams();
  if (filters.division) params.set("division", filters.division);
  if (filters.ownership) params.set("ownership", filters.ownership);
  if (filters.equipmentType) params.set("equipment_type", filters.equipmentType);
  if (filters.jobId) params.set("job_id", filters.jobId);
  const query = params.size ? `?${params.toString()}` : "";
  const response = await fetch(`/api/equipment${query}`);
  return responseJson<EquipmentDashboard>(response);
}
