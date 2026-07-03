export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">▲ KYLE TRADER</div>

      <nav className="sidebar-nav">
        <div className="nav-item active">Dashboard</div>
        <div className="nav-item">Watchlist</div>
        <div className="nav-item">Positions</div>
        <div className="nav-item">Orders</div>
        <div className="nav-item">Analytics</div>
        <div className="nav-item">Settings</div>
      </nav>

      <div className="capital-card">
        <span>Starting Capital</span>
        <strong>$10,000.00</strong>
      </div>
    </aside>
  );
}