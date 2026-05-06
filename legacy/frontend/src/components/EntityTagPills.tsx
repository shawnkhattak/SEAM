import type { NewsEntity } from "../api/news";

interface EntityTagPillsProps {
  entities: NewsEntity[];
  onEntityClick?: (entity: NewsEntity) => void;
}

const TYPE_STYLES: Record<string, string> = {
  vessel: "bg-teal-50 border-teal-200 text-teal-700 hover:bg-teal-100",
  port: "bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100",
};

const TYPE_LABELS: Record<string, string> = {
  vessel: "vessel",
  port: "port",
};

export function EntityTagPills({ entities, onEntityClick }: EntityTagPillsProps) {
  if (!entities.length) return null;

  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {entities.map((entity, i) => {
        const style = TYPE_STYLES[entity.entity_type] ?? "bg-slate-50 border-slate-200 text-slate-700";
        return (
          <button
            key={`${entity.entity_type}-${entity.entity_ref_id}-${i}`}
            onClick={() => onEntityClick?.(entity)}
            className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border transition-colors ${style} ${onEntityClick ? "cursor-pointer" : "cursor-default"}`}
            title={`${TYPE_LABELS[entity.entity_type] ?? entity.entity_type} · ID ${entity.entity_ref_id}`}
          >
            <span className="opacity-60 text-[10px] uppercase tracking-wide">
              {TYPE_LABELS[entity.entity_type] ?? entity.entity_type}
            </span>
            <span className="font-medium">{entity.matched_text}</span>
          </button>
        );
      })}
    </div>
  );
}
