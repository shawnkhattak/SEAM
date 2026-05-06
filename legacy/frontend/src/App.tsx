import { lazy, Suspense } from "react";
import { LiveMap } from "./components/LiveMap";

const AdminApp = lazy(() =>
  import("./components/admin/AdminApp").then((m) => ({ default: m.AdminApp }))
);

function isAdminRoute() {
  return (
    window.location.pathname === "/admin" ||
    window.location.hash === "#admin"
  );
}

export default function App() {
  if (isAdminRoute()) {
    return (
      <Suspense fallback={<div className="min-h-screen bg-slate-950 text-slate-500 flex items-center justify-center text-sm">Loading admin…</div>}>
        <AdminApp />
      </Suspense>
    );
  }

  return (
    <div className="h-screen overflow-hidden bg-[var(--bg-base)]">
      <LiveMap />
    </div>
  );
}
