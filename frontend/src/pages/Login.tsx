/** Login + register, one centered card. */

import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LogoIcon } from "../components/icons";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name);
      const from = (location.state as { from?: string } | null)?.from ?? "/";
      navigate(from, { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center px-5">
      <div className="w-full max-w-[380px]">
        <div className="mb-7 flex items-center justify-center gap-3">
          <span
            className="grid place-items-center rounded-xl"
            style={{
              width: 42,
              height: 42,
              background: "linear-gradient(135deg, var(--accent), #9C63F2)",
              boxShadow: "0 4px 14px -4px color-mix(in srgb, var(--accent) 70%, transparent)",
            }}
          >
            <LogoIcon size={20} />
          </span>
          <span className="text-[22px] font-extrabold tracking-tight">Collector</span>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3.5 rounded-2xl bg-surface p-7 shadow-card">
          <h1 className="m-0 text-lg font-extrabold tracking-tight">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h1>
          {mode === "register" && (
            <label className="field">
              Name
              <input required value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
            </label>
          )}
          <label className="field">
            Email
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </label>
          <label className="field">
            Password
            <input
              required
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>
          {error && <p className="m-0 text-[13px] text-movie">{error}</p>}
          <button type="submit" className="btn mt-1" disabled={busy}>
            {busy ? "One moment…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
            className="text-[13px] text-muted hover:text-text"
          >
            {mode === "login" ? "New here? Create an account" : "Have an account? Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
