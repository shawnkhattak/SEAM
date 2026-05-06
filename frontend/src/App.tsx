import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

const LiveMap = lazy(() =>
  import("./components/LiveMap").then((m) => ({ default: m.LiveMap }))
);

const AdminApp = lazy(() =>
  import("./components/admin/AdminApp").then((m) => ({ default: m.AdminApp }))
);

const VesselInspector = lazy(() =>
  import("./components/VesselInspector").then((m) => ({ default: m.VesselInspector }))
);

const Loading = () => (
  <div className="min-h-screen bg-slate-950 text-slate-500 flex items-center justify-center text-sm">
    Loading…
  </div>
);

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<LiveMap />} />
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="/vessels/:imo" element={<VesselInspector />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
