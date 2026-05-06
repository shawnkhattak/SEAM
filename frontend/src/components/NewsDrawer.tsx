import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, Loader2, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { fetchNewsSummary } from "../api/intelligence";
import { fetchNews } from "../api/news";
import type { NewsEntity, NewsItem as NewsItemType } from "../api/news";
import type { NewsSummaryResponse } from "../types";
import { EntityTagPills } from "./EntityTagPills";

interface NewsDrawerProps {
  onClose: () => void;
  filterEntityType?: string;
  filterEntityRefId?: number;
  filterLabel?: string;
}

function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ArticleCard({
  item,
  onEntityClick,
}: {
  item: NewsItemType;
  onEntityClick: (e: NewsEntity) => void;
}) {
  const [summary, setSummary] = useState<NewsSummaryResponse | null>(null);
  const [showSummary, setShowSummary] = useState(false);

  const { mutate, isPending } = useMutation({
    mutationFn: () => fetchNewsSummary(item.id),
    onSuccess: (data) => {
      setSummary(data);
      setShowSummary(true);
    },
  });

  function handleSummarize(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (summary) {
      setShowSummary((v) => !v);
    } else {
      mutate();
    }
  }

  return (
    <li className="px-4 py-3 transition-colors hover:bg-white/60">
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex items-start justify-between gap-2"
      >
        <span className="text-sm leading-snug text-[var(--text-primary)] group-hover:text-[var(--accent-deep)]">
          {item.title}
        </span>
        <ExternalLink
          size={12}
          className="mt-0.5 shrink-0 text-[var(--text-muted)] group-hover:text-[var(--accent-deep)]"
        />
      </a>
      <div className="mt-1 flex items-center gap-2 text-xs text-[var(--text-muted)]">
        <span>{relativeTime(item.published_at_utc)}</span>
        <button
          onClick={handleSummarize}
          disabled={isPending}
          className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-xs transition-colors ${
            showSummary
              ? "bg-teal-50 text-teal-700"
              : "text-[var(--text-muted)] hover:bg-white/70 hover:text-[var(--text-primary)]"
          }`}
          title={summary ? "Toggle AI summary" : "Generate AI summary"}
          aria-label="Summarize article"
        >
          {isPending ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
          <span>Summary</span>
        </button>
      </div>
      {item.entities.length > 0 && (
        <EntityTagPills entities={item.entities} onEntityClick={onEntityClick} />
      )}
      {showSummary && summary && (
        <div className="mt-2 rounded border border-teal-100 bg-teal-50/70 px-2 py-2 text-xs leading-relaxed text-[var(--text-secondary)]">
          {summary.summary_text}
        </div>
      )}
    </li>
  );
}

export function NewsDrawer({
  onClose,
  filterEntityType,
  filterEntityRefId,
  filterLabel,
}: NewsDrawerProps) {
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["news", filterEntityType, filterEntityRefId],
    queryFn: () =>
      fetchNews({
        limit: 50,
        entity_type: filterEntityType,
        entity_ref_id: filterEntityRefId,
      }),
    staleTime: 120_000,
    refetchInterval: 300_000,
  });

  function handleEntityClick(_entity: NewsEntity) {
    // future: filter by entity
  }

  return (
    <div className="left-drawer-panel glass-panel-bright absolute bottom-0 left-0 top-11 z-[600] flex w-96 max-w-[calc(100vw-1rem)] flex-col overflow-hidden rounded-none border-y-0 border-l-0 shadow-2xl">
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Maritime News</h2>
          {filterLabel && (
            <p className="mt-0.5 text-xs text-[var(--text-muted)]">Filtered: {filterLabel}</p>
          )}
        </div>
        <button
          onClick={onClose}
          className="rounded border border-[var(--border)] p-1 text-[var(--text-secondary)] transition-colors hover:border-[var(--border-accent)] hover:bg-white"
          aria-label="Close news drawer"
        >
          <X size={16} />
        </button>
      </div>

      <div className="thin-scroll flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-3 p-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="animate-pulse space-y-2">
                <div className="h-4 w-3/4 rounded bg-slate-200" />
                <div className="h-3 w-1/3 rounded bg-slate-100" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="p-6 text-center text-sm text-[var(--text-muted)]">No articles yet.</div>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {items.map((item) => (
              <ArticleCard key={item.id} item={item} onEntityClick={handleEntityClick} />
            ))}
          </ul>
        )}
      </div>

      <div className="shrink-0 border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--text-muted)]">
        {items.length} article{items.length !== 1 ? "s" : ""} · refreshes every 5 min
      </div>
    </div>
  );
}
