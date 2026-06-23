import { FormEvent, useState } from "react";

import { useAuth, usePostLoginRedirect } from "../lib/auth";

export function Login() {
  const { login } = useAuth();
  const redirect = usePostLoginRedirect();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const session = await login({ email, password });
      redirect(session);
    } catch {
      setError("Invalid email or password.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-zinc-50 px-4 text-zinc-950">
      <form className="w-full max-w-sm space-y-4" onSubmit={onSubmit}>
        <h1 className="text-2xl font-semibold">Clinic scheduling</h1>
        <label className="block text-sm font-medium">
          Email
          <input
            className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input
            className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
        <button className="w-full rounded bg-emerald-700 px-4 py-2 font-medium text-white" type="submit">
          Sign in
        </button>
      </form>
    </main>
  );
}
