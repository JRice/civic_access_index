const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function fetchHealth() {
  const response = await fetch(`${API_BASE}/healthz`);
  return response.json();
}

export async function fetchTractExplanation(geoid: string) {
  const response = await fetch(`${API_BASE}/api/tracts/${geoid}/explanation`);
  return response.json();
}

