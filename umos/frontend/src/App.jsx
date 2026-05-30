import { BrowserRouter, Routes, Route } from "react-router-dom";
import RoutePlanner from "./pages/RoutePlanner.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import EquityView from "./pages/EquityView.jsx";
import AlertCenter from "./pages/AlertCenter.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RoutePlanner />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/equity" element={<EquityView />} />
        <Route path="/alerts" element={<AlertCenter />} />
      </Routes>
    </BrowserRouter>
  );
}
