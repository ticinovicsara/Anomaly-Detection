import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, LogIn } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { useToast } from "../components/Toast";
import { auth, errorMessage } from "../api/client";
import { useAuth } from "../hooks/useAuth";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();
  const nav = useNavigate();
  const { refresh } = useAuth();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await auth.login(email, password);
      localStorage.setItem("token", r.data.access_token);
      await refresh();
      toast({ tone: "success", title: "Welcome back" });
      nav("/");
    } catch (err) {
      toast({
        tone: "error",
        title: "Login failed",
        message: errorMessage(err, "Check your credentials"),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <div className="w-full max-w-md animate-fade-in">
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="rounded-xl bg-accent/10 p-2 text-accent">
            <Activity className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-text">Anomaly Detection</h1>
        </div>

        <Card className="p-8">
          <h2 className="text-lg font-semibold text-text">Sign in</h2>
          <p className="mt-1 text-sm text-muted">Welcome back. Enter your details to continue.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={6}
            />
            <Button type="submit" loading={loading} icon={<LogIn className="h-4 w-4" />} className="w-full">
              Sign in
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            No account?{" "}
            <Link to="/register" className="font-medium text-accent hover:underline">
              Create one
            </Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
