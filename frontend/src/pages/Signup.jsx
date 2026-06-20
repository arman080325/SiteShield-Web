import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import AuthForm from "../components/AuthForm";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSignup(email, password) {
    setError(null);
    setLoading(true);
    try {
      await signup(email, password); // context auto-logs-in after
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center">
      <h1 className="text-2xl font-bold mb-1">Create your account</h1>
      <p className="text-sm text-zinc-500 mb-6">Start auditing your site's security</p>
      <AuthForm mode="signup" onSubmit={handleSignup} error={error} loading={loading} />
      <p className="mt-4 text-sm text-zinc-500">
        Already have an account?{" "}
        <Link to="/login" className="text-emerald-600 hover:underline">
          Log in
        </Link>
      </p>
    </div>
  );
}