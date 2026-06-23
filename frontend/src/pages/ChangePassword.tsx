import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth";

export function ChangePassword() {
  const { changePassword } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await changePassword({ currentPassword, newPassword });
      navigate("/", { replace: true });
    } catch {
      setError("Password could not be changed.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-zinc-50 px-4 text-zinc-950">
      <form className="w-full max-w-sm space-y-4" onSubmit={onSubmit}>
        <h1 className="text-2xl font-semibold">Change password</h1>
        <label className="block text-sm font-medium">
          Current password
          <input
            className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
          />
        </label>
        <label className="block text-sm font-medium">
          New password
          <input
            className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            minLength={8}
            required
          />
        </label>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
        <button className="w-full rounded bg-emerald-700 px-4 py-2 font-medium text-white" type="submit">
          Update password
        </button>
      </form>
    </main>
  );
}
