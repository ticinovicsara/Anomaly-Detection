import { useEffect, useState } from "react";
import { auth } from "../api/client";

export function useAuth() {
  const [user, setUser] = useState<{ id: number; email: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem("token");

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    auth
      .me()
      .then((r) => setUser(r.data))
      .catch(() => {
        localStorage.removeItem("token");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  return { user, loading, isAuthed: !!user };
}

export function logout() {
  localStorage.removeItem("token");
  window.location.href = "/login";
}
