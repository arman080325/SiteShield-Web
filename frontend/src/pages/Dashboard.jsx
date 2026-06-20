import { useAuth } from "../context/AuthContext";

export default function Dashboard() {
  const { user } = useAuth();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Dashboard</h1>
      <p className="text-zinc-500">
        Logged in as <span className="font-medium">{user?.email}</span>.
        Domain management and scanning coming next.
      </p>
    </div>
  );
}