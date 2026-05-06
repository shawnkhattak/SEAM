const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface JournalPhase {
  phase_number: number;
  title: string;
  started_at: string | null;
  completed_at: string | null;
  summary_md: string | null;
  markdown_file_path: string | null;
  indexed_at: string;
}

export interface JournalAdr {
  adr_number: number;
  title: string;
  status: string;
  decided_at: string | null;
  summary_md: string | null;
  markdown_file_path: string | null;
  superseded_by_adr_number: number | null;
  indexed_at: string;
}

export interface GlossaryTerm {
  term: string;
  category: string | null;
  plain_definition: string | null;
  why_it_matters_in_project: string | null;
  markdown_file_path: string | null;
  indexed_at: string;
}

export async function fetchPhases(): Promise<JournalPhase[]> {
  const res = await fetch(`${BASE}/api/journal/phases`);
  if (!res.ok) throw new Error(`journal/phases fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchAdrs(): Promise<JournalAdr[]> {
  const res = await fetch(`${BASE}/api/journal/adrs`);
  if (!res.ok) throw new Error(`journal/adrs fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchGlossary(): Promise<GlossaryTerm[]> {
  const res = await fetch(`${BASE}/api/journal/glossary`);
  if (!res.ok) throw new Error(`journal/glossary fetch failed: ${res.status}`);
  return res.json();
}
