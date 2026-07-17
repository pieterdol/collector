import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, BrowserRouter, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { AppShell } from "./components/AppShell";
import { AuthProvider, useAuth } from "./lib/auth";
import AddItem from "./pages/AddItem";
import ItemDetail from "./pages/ItemDetail";
import Login from "./pages/Login";
import Shelf from "./pages/Shelf";
import SteamImport from "./pages/SteamImport";
import Wishlist from "./pages/Wishlist";
import { applyStoredTheme } from "./theme/useTheme";

applyStoredTheme();

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="skeleton h-10 w-10 rounded-full" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              element={
                <RequireAuth>
                  <AppShell />
                </RequireAuth>
              }
            >
              <Route path="/" element={<Shelf />} />
              <Route path="/wishlist" element={<Wishlist />} />
              <Route path="/add" element={<AddItem />} />
              <Route path="/steam" element={<SteamImport />} />
              <Route path="/items/:id" element={<ItemDetail />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
