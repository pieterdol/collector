/** App layout: icon rail (left on desktop, bottom bar on mobile) + top bar. */

import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/auth";
import { useTheme } from "../theme/useTheme";
import {
  GridIcon,
  HeartIcon,
  LogoIcon,
  MoonIcon,
  PlusIcon,
  SearchIcon,
  SteamIcon,
  SunIcon,
} from "./icons";

const NAV = [
  { to: "/", label: "Shelf", icon: GridIcon },
  { to: "/wishlist", label: "Wishlist", icon: HeartIcon },
  { to: "/add", label: "Add to collection", icon: PlusIcon },
  { to: "/steam", label: "Import from Steam", icon: SteamIcon },
];

export function AppShell() {
  return (
    <div className="flex min-h-screen max-[760px]:flex-col">
      <Rail />
      <div className="min-w-0 flex-1">
        <TopBar />
        <main className="mx-auto max-w-[1240px] px-7 pb-24 pt-3 max-[760px]:px-4 max-[760px]:pb-28">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function Rail() {
  return (
    <aside
      className="sticky top-0 z-50 flex h-screen w-16 flex-none flex-col items-center gap-1.5 border-r border-line-soft bg-rail py-3.5
        max-[760px]:fixed max-[760px]:inset-x-0 max-[760px]:bottom-0 max-[760px]:top-auto max-[760px]:h-auto max-[760px]:w-full
        max-[760px]:flex-row max-[760px]:justify-around max-[760px]:border-r-0 max-[760px]:border-t max-[760px]:px-3.5
        max-[760px]:pb-[calc(8px+env(safe-area-inset-bottom))] max-[760px]:pt-2"
    >
      <div
        className="mb-3.5 grid h-9.5 w-9.5 flex-none place-items-center rounded-xl max-[760px]:hidden"
        style={{
          width: 38,
          height: 38,
          background: "linear-gradient(135deg, var(--accent), #9C63F2)",
          boxShadow: "0 4px 14px -4px color-mix(in srgb, var(--accent) 70%, transparent)",
        }}
        title="Collector"
      >
        <LogoIcon />
      </div>
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          title={label}
          className={({ isActive }) =>
            `grid h-[42px] w-[42px] place-items-center rounded-xl transition-colors ${
              isActive ? "bg-accent text-white" : "text-faint hover:bg-surface hover:text-text"
            }`
          }
        >
          <Icon />
        </NavLink>
      ))}
    </aside>
  );
}

function TopBar() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const showSearch = location.pathname === "/" || location.pathname === "/wishlist";

  return (
    <div className="flex items-center gap-3.5 px-7 pb-1 pt-4 max-[760px]:px-4">
      <div className="w-24 flex-none max-[760px]:hidden" />
      <div className="mx-auto w-full max-w-[460px]">{showSearch && <SearchBox />}</div>
      <div className="flex w-24 flex-none items-center justify-end gap-1 max-[760px]:w-auto">
        <button
          type="button"
          onClick={toggle}
          title="Switch theme"
          aria-label="Switch theme"
          className="grid h-9.5 w-9.5 place-items-center rounded-full text-muted transition-colors hover:bg-surface hover:text-text"
          style={{ width: 38, height: 38 }}
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
        <UserMenu name={user?.display_name ?? "?"} onLogout={logout} />
      </div>
    </div>
  );
}

/** Search box bound to the ?q= URL param (shared by shelf and wishlist). */
function SearchBox() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [value, setValue] = useState(params.get("q") ?? "");

  // Keep local state in sync when the URL changes (e.g. back button).
  useEffect(() => setValue(params.get("q") ?? ""), [params]);

  // Debounce typing into the URL.
  useEffect(() => {
    const handle = setTimeout(() => {
      const current = params.get("q") ?? "";
      if (value === current) return;
      const next = new URLSearchParams(params);
      if (value) next.set("q", value);
      else next.delete("q");
      if (location.pathname === "/" || location.pathname === "/wishlist") {
        setParams(next, { replace: true });
      } else {
        navigate(`/?${next.toString()}`);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative">
      <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 opacity-45" />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search your collection…"
        className="w-full rounded-full border border-line bg-surface py-2.5 pl-9.5 pr-4 text-sm outline-none transition-colors focus:border-accent"
        style={{ paddingLeft: 38 }}
      />
    </div>
  );
}

function UserMenu({ name, onLogout }: { name: string; onLogout: () => void }) {
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
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Account"
        className="grid place-items-center rounded-full font-bold text-white"
        style={{
          width: 36,
          height: 36,
          background: "linear-gradient(135deg, var(--accent), #9C63F2)",
          fontSize: 14,
        }}
      >
        {name.charAt(0).toUpperCase()}
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-50 w-44 rounded-xl border border-line bg-raised p-1.5 shadow-lift">
          <div className="px-3 py-2 text-[13px] font-semibold">{name}</div>
          <button
            type="button"
            onClick={onLogout}
            className="w-full rounded-lg px-3 py-2 text-left text-[13px] text-muted transition-colors hover:bg-surface hover:text-text"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
