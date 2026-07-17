/** App layout, graphite design: 232px labeled sidebar (bottom bar on
 * mobile) + a per-page header with search, view toggle and actions. */

import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/auth";
import { useTheme } from "../theme/useTheme";
import {
  ChartIcon,
  GridIcon,
  HeartIcon,
  LogoIcon,
  MoonIcon,
  RowsIcon,
  SearchIcon,
  SteamIcon,
  SunIcon,
} from "./icons";

const NAV = [
  { to: "/", label: "Library", icon: GridIcon },
  { to: "/stats", label: "Stats", icon: ChartIcon },
  { to: "/wishlist", label: "Wishlist", icon: HeartIcon },
  { to: "/steam", label: "Import", icon: SteamIcon },
];

const TITLES: Record<string, string> = {
  "/": "Library",
  "/stats": "Stats",
  "/wishlist": "Wishlist",
  "/add": "Add item",
  "/steam": "Import from Steam",
};

export function AppShell() {
  return (
    <div className="flex min-h-screen max-[820px]:flex-col">
      <Sidebar />
      <div className="min-w-0 flex-1">
        <main className="flex flex-col gap-6 px-8 pb-14 pt-7 max-[820px]:px-4 max-[820px]:pb-28">
          <PageHeader />
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function Sidebar() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  return (
    <aside
      className="sticky top-0 z-50 flex h-screen w-[232px] flex-none flex-col gap-7 border-r border-line bg-bg px-4 py-6
        max-[820px]:fixed max-[820px]:inset-x-0 max-[820px]:bottom-0 max-[820px]:top-auto max-[820px]:h-auto max-[820px]:w-full
        max-[820px]:flex-row max-[820px]:items-center max-[820px]:justify-around max-[820px]:gap-1 max-[820px]:border-r-0
        max-[820px]:border-t max-[820px]:px-3 max-[820px]:pb-[calc(6px+env(safe-area-inset-bottom))] max-[820px]:pt-1.5"
    >
      <div className="flex items-center gap-2.5 px-2 max-[820px]:hidden">
        <span
          className="grid place-items-center rounded-lg"
          style={{ width: 30, height: 30, background: "linear-gradient(135deg, var(--accent), oklch(70% 0.16 310))" }}
        >
          <LogoIcon size={15} />
        </span>
        <span className="font-display text-[17px] font-semibold tracking-[0.02em]">Collector</span>
      </div>

      <nav className="flex flex-col gap-0.5 max-[820px]:flex-1 max-[820px]:flex-row max-[820px]:justify-around max-[820px]:gap-0">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm no-underline transition-colors
               max-[820px]:flex-col max-[820px]:gap-1 max-[820px]:px-3 max-[820px]:py-1.5 max-[820px]:text-[10px] ${
                 isActive ? "bg-raised/60 font-semibold text-text" : "text-muted hover:bg-surface"
               }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className="h-[7px] w-[7px] flex-none rounded-[2px] max-[820px]:hidden"
                  style={{ background: isActive ? "var(--accent)" : "var(--nav-dot)" }}
                />
                <Icon size={15} className="hidden max-[820px]:block" />
                <span>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-1 max-[820px]:hidden">
        <button
          type="button"
          onClick={toggle}
          className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted transition-colors hover:bg-surface"
        >
          {theme === "dark" ? <SunIcon size={14} /> : <MoonIcon size={14} />}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <UserRow name={user?.display_name ?? "?"} onLogout={logout} />
      </div>
    </aside>
  );
}

function UserRow({ name, onLogout }: { name: string; onLogout: () => void }) {
  const [confirm, setConfirm] = useState(false);
  return (
    <div className="flex items-center gap-2.5 rounded-lg px-2.5 py-2">
      <span
        className="grid h-6 w-6 flex-none place-items-center rounded-full text-[11px] font-bold text-white"
        style={{ background: "linear-gradient(135deg, var(--accent), oklch(70% 0.16 310))" }}
      >
        {name.charAt(0).toUpperCase()}
      </span>
      <span className="min-w-0 flex-1 truncate text-sm text-body">{name}</span>
      {confirm ? (
        <button type="button" onClick={onLogout} className="text-xs font-semibold text-danger">
          Sign out?
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setConfirm(true)}
          onBlur={() => setConfirm(false)}
          title="Sign out"
          className="text-xs text-faint hover:text-text"
        >
          ⏻
        </button>
      )}
    </div>
  );
}

function PageHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [params, setParams] = useSearchParams();

  const onLibrary = location.pathname === "/";
  const onDetail = location.pathname.startsWith("/items/");
  const title = TITLES[location.pathname] ?? "Library";
  const showSearch = onLibrary || location.pathname === "/wishlist";
  const view = params.get("view") ?? "grid";

  if (onDetail) return null; // the detail page brings its own header

  function setView(next: "grid" | "table") {
    const nextParams = new URLSearchParams(params);
    if (next === "grid") nextParams.delete("view");
    else nextParams.set("view", "table");
    setParams(nextParams, { replace: true });
  }

  return (
    <header className="flex flex-wrap items-center gap-4">
      <h1 className="m-0 font-display text-2xl font-semibold tracking-[-0.01em]">{title}</h1>
      {showSearch && <SearchBox />}
      <div className="ml-auto flex items-center gap-2.5">
        {onLibrary && (
          <div className="flex gap-0.5 rounded-[9px] border border-line bg-surface p-0.5">
            <button
              type="button"
              aria-pressed={view === "grid"}
              onClick={() => setView("grid")}
              title="Gallery"
              className={`flex items-center gap-1.5 rounded-[7px] px-2.5 py-1.5 text-xs font-semibold ${
                view === "grid" ? "bg-raised text-text" : "text-faint"
              }`}
            >
              <GridIcon size={12} /> Gallery
            </button>
            <button
              type="button"
              aria-pressed={view === "table"}
              onClick={() => setView("table")}
              title="Table"
              className={`flex items-center gap-1.5 rounded-[7px] px-2.5 py-1.5 text-xs font-semibold ${
                view === "table" ? "bg-raised text-text" : "text-faint"
              }`}
            >
              <RowsIcon size={12} /> Table
            </button>
          </div>
        )}
        <button type="button" className="btn btn-ghost max-[560px]:hidden" onClick={() => navigate("/add?mode=scan")}>
          <span className="font-mono text-xs">[|||]</span> Scan
        </button>
        <button type="button" className="btn" onClick={() => navigate("/add")}>
          + Add item
        </button>
        <button
          type="button"
          onClick={toggle}
          title="Switch theme"
          aria-label="Switch theme"
          className="hidden h-9 w-9 place-items-center rounded-[9px] text-muted hover:bg-surface max-[820px]:grid"
        >
          {theme === "dark" ? <SunIcon size={15} /> : <MoonIcon size={15} />}
        </button>
        <MobileUser name={user?.display_name ?? "?"} onLogout={logout} />
      </div>
    </header>
  );
}

/** Search box bound to the ?q= URL param (library + wishlist). */
function SearchBox() {
  const [params, setParams] = useSearchParams();
  const [value, setValue] = useState(params.get("q") ?? "");

  useEffect(() => setValue(params.get("q") ?? ""), [params]);

  useEffect(() => {
    const handle = setTimeout(() => {
      const current = params.get("q") ?? "";
      if (value === current) return;
      const next = new URLSearchParams(params);
      if (value) next.set("q", value);
      else next.delete("q");
      setParams(next, { replace: true });
    }, 250);
    return () => clearTimeout(handle);
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative min-w-[220px] flex-1" style={{ maxWidth: 420 }}>
      <SearchIcon size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 opacity-50" />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search titles, authors, directors…"
        className="input w-full"
        style={{ paddingLeft: 36 }}
      />
    </div>
  );
}

function MobileUser({ name, onLogout }: { name: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div className="relative hidden max-[820px]:block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Account"
        className="grid h-9 w-9 place-items-center rounded-full text-[13px] font-bold text-white"
        style={{ background: "linear-gradient(135deg, var(--accent), oklch(70% 0.16 310))" }}
      >
        {name.charAt(0).toUpperCase()}
      </button>
      {open && (
        <div className="panel absolute right-0 top-11 z-50 w-44 p-1.5 shadow-lift">
          <div className="px-3 py-2 text-[13px] font-semibold">{name}</div>
          <button
            type="button"
            onClick={onLogout}
            className="w-full rounded-lg px-3 py-2 text-left text-[13px] text-muted hover:bg-raised hover:text-text"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
