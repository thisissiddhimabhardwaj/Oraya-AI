import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  BookOpen,
  CalendarDays,
  ChartNoAxesCombined,
  ChevronRight,
  Compass,
  GitCompare,
  GraduationCap,
  HelpCircle,
  Home,
  Layers,
  LogOut,
  Menu,
  MessageSquare,
  Network,
  Plus,
  Sparkles,
  Users,
  X,
  UserRound,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import "./AppShell.css";
const groups = [
  {
    label: "YOUR LEARNING",
    links: [
      ["/dashboard", "Overview", Home],
      ["/library", "Learning library", BookOpen],
      ["/ask", "Ask my library", MessageSquare],
    ],
  },
  {
    label: "PRACTISE & GROW",
    links: [
      ["/flashcards", "Flashcards", Layers],
      ["/revision", "Smart revision", Sparkles],
      ["/exams", "Exam mode", GraduationCap],
      ["/planner", "Study planner", CalendarDays],
      ["/progress", "Your progress", ChartNoAxesCombined],
    ],
  },
  {
    label: "GO FURTHER",
    links: [
      ["/spatial", "Spatial studio", Compass],
      ["/memory", "Learning profile", UserRound],
    ],
  },
];
export function AppShell() {
  const { user, logout } = useAuth(),
    location = useLocation(),
    navigate = useNavigate();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setOpen(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    const close = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, []);
  const current =
    groups
      .flatMap((g) => g.links)
      .find((l) => l[0] === location.pathname)?.[1] ||
    (location.pathname.startsWith("/lecture")
      ? "Learning workspace"
      : "New material");
  return (
    <div className="oraya-app">
      <a className="app-skip" href="#main-content">
        Skip to content
      </a>
      {open && (
        <button
          className="app-sidebar-shade"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={`app-sidebar ${open ? "is-open" : ""}`}>
        <div className="app-sidebar-brand">
          <Link to="/dashboard">
            <span>✦</span> ORAYA
          </Link>
          <button
            className="app-mobile-close"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <p className="app-brand-tagline">BEYOND THE CLASSROOM</p>
        <Link className="app-add-material" to="/learn/new">
          <Plus size={17} /> Add learning material
        </Link>
        <nav aria-label="Main navigation">
          {groups.map((g) => (
            <div className="app-nav-group" key={g.label}>
              <p>{g.label}</p>
              {g.links.map(([to, label, Icon]) => (
                <NavLink
                  to={to}
                  key={to}
                  className={({ isActive }) => (isActive ? "active" : "")}
                >
                  <Icon size={17} strokeWidth={1.6} />
                  <span>{label}</span>
                  <ChevronRight className="app-active-arrow" size={13} />
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="app-sidebar-foot">
          <div className="app-curiosity">
            <span>✧</span>
            <p>
              A little curiosity.
              <br />A whole new world.
            </p>
          </div>
          <button
            onClick={async () => {
              await logout();
              navigate("/login", { replace: true });
            }}
          >
            <LogOut size={15} /> Log out
          </button>
        </div>
      </aside>
      <div className="app-body">
        <header className="app-topbar">
          <button
            className="app-menu-toggle"
            aria-label="Open navigation"
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            <Menu size={21} />
          </button>
          <div className="app-breadcrumb">
            Your learning space <ChevronRight size={12} />
            <span>{current}</span>
          </div>
          <details className="app-profile-menu">
            <summary className="app-profile" aria-label="Your account menu">
              <span>{user?.name?.slice(0, 1).toUpperCase()}</span>
              <div>
                {user?.name}
                <small>Keep being curious.</small>
              </div>
            </summary>
            <div className="app-account-popover">
              <Link to="/memory">
                <UserRound size={15} />
                Profile & account settings
              </Link>
              <button
                onClick={async () => {
                  await logout();
                  navigate("/login", { replace: true });
                }}
              >
                <LogOut size={15} />
                Log out
              </button>
            </div>
          </details>
        </header>
        <main id="main-content" tabIndex={-1} className="app-content">
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>✦ ORAYA</span>
          <p>Every question is a beginning.</p>
          <Link to="/memory">Your learning, your data ↗</Link>
        </footer>
      </div>
    </div>
  );
}
