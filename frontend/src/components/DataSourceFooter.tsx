import { TimeZoneSelector } from "./TimeZoneSelector";

export function DataSourceFooter() {
  return (
    <footer className="fixed bottom-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-1.5 bg-slate-900/90 border-t border-slate-700 text-xs text-slate-400">
      <span>
        Sanctions:{" "}
        <a
          href="https://opensanctions.org"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-slate-200"
        >
          OpenSanctions.org
        </a>{" "}
        · Weather:{" "}
        <a
          href="https://open-meteo.com"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-slate-200"
        >
          Open-Meteo.com
        </a>{" "}
        · Vessels:{" "}
        <a
          href="https://oceans-x.mpa.gov.sg"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-slate-200"
        >
          MPA Singapore
        </a>
      </span>
      <TimeZoneSelector />
    </footer>
  );
}
