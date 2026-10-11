import type { ActiveFilters, PortfolioDashboard } from "./types";

export async function fetchPortfolio(filters: ActiveFilters): Promise<PortfolioDashboard> {
  const params = new URLSearchParams();
  if (filters.division) params.set("division", filters.division);
  if (filters.contractType) params.set("contract_type", filters.contractType);
  if (filters.projectManager) params.set("project_manager_id", filters.projectManager);
  if (filters.progressStatus) params.set("progress_status", filters.progressStatus);

  const query = params.size ? `?${params.toString()}` : "";
  const response = await fetch(`/api/portfolio${query}`);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Dashboard API returned ${response.status}`);
  }
  return (await response.json()) as PortfolioDashboard;
}
