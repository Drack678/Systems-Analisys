import { BrowserRouter, Routes, Route } from "react-router-dom";
import MapPage from "./pages/MapPage.jsx?v=tm";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MapPage />} />
      </Routes>
    </BrowserRouter>
  );
}
