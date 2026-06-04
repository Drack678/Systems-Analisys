import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/", label: "Route Planner", icon: "🗺" },
  { to: "/dashboard", label: "Dashboard", icon: "📡" },
  { to: "/equity", label: "Equity", icon: "⚖️" },
  { to: "/alerts", label: "Alerts", icon: "🔔" },
];

export default function AppNav() {
  return (
    <nav style={{
      display: "flex", gap: 2, padding: "0.5rem 0.75rem",
      borderBottom: "1px solid var(--border)", background: "var(--surface)",
      flexWrap: "wrap",
    }}>
      {LINKS.map(({ to, label, icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          style={({ isActive }) => ({
            padding: "0.4rem 0.65rem",
            borderRadius: 6,
            fontSize: "0.75rem",
            fontWeight: 600,
            textDecoration: "none",
            color: isActive ? "var(--electric)" : "var(--text-muted)",
            background: isActive ? "#0a1628" : "transparent",
            whiteSpace: "nowrap",
          })}
        >
          {icon} {label}
        </NavLink>
      ))}
    </nav>
  );
}
