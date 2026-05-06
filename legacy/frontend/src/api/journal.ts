import axios from "axios";

const api = axios.create({ baseURL: "/api" });

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
  const { data } = await api.get<JournalPhase[]>("/journal/phases");
  return data;
}

export async function fetchAdrs(): Promise<JournalAdr[]> {
  const { data } = await api.get<JournalAdr[]>("/journal/adrs");
  return data;
}

export async function fetchGlossary(): Promise<GlossaryTerm[]> {
  const { data } = await api.get<GlossaryTerm[]>("/journal/glossary");
  return data;
}
