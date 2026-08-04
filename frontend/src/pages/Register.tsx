import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, UserPlus } from "lucide-react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { useToast } from "../components/Toast";
import { auth, errorMessage } from "../api/client";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const toast = useToast();
  const nav = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await auth.register(email, password);
      const r = await auth.login(email, password);
      localStorage.setItem("token", r.data.access_token);
      toast({ tone: "success", title: "Account created" });
      nav("/");
    } catch (err) {
      toast({
        tone: "error",
        title: "Registration failed",
        message: errorMessage(err, "Try a different email"),
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
          <h2 className="text-lg font-semibold text-text">Create account</h2>
          <p className="mt-1 text-sm text-muted">Get started in seconds — no credit card needed.</p>

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
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="minimum 6 characters"
              required
              minLength={6}
            />
            <Button type="submit" loading={loading} icon={<UserPlus className="h-4 w-4" />} className="w-full">
              Create account
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            Already have an account?{" "}
            <Link to="/login" className="font-medium text-accent hover:underline">
              Sign in
            </Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
