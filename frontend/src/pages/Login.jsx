import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import AuthForm from "../components/AuthForm";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin(email, password) {
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/"); // success → go to dashboard
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center">
      <h1 className="text-2xl font-bold mb-1">Welcome back</h1>
      <p className="text-sm text-zinc-500 mb-6">Log in to your SiteShield account</p>
      <AuthForm mode="login" onSubmit={handleLogin} error={error} loading={loading} />
      <p className="mt-4 text-sm text-zinc-500">
        No account?{" "}
        <Link to="/signup" className="text-emerald-600 hover:underline">
          Sign up
        </Link>
      </p>
    </div>
  );
}