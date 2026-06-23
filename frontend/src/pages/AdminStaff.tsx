import { useState } from "react";

import { useCreateUser, useUpdateUser, useUsers } from "../api/hooks/users";
import { Abbr } from "../components/Abbr";
import type { User, UserCreate } from "../api/generated";

const ROLE_LABELS: Record<string, string> = {
  doctor: "Doctor",
  reception: "Reception",
  center_admin: "Center admin"
};

const EMPTY_FORM = {
  role: "doctor" as const,
  email: "",
  display_name: "",
  temp_password: "",
  specialty: ""
};

/** T075 — center-admin staff management: list, create-with-temp-password, edit display name,
 *  deactivate/reactivate. Staff are center-scoped server-side (FR-019..FR-022). */
export function AdminStaff() {
  const users = useUsers();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();

  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string; display_name: string } | null>(null);

  async function submitCreate() {
    if (!form.email.trim() || !form.display_name.trim() || form.temp_password.length < 8) {
      setError("Email, display name, and a temporary password (≥8 characters) are required.");
      return;
    }
    setError(null);
    const body: UserCreate = {
      role: form.role,
      email: form.email.trim(),
      display_name: form.display_name.trim(),
      temp_password: form.temp_password,
      specialty: form.role === "doctor" && form.specialty.trim() ? form.specialty.trim() : undefined
    };
    const result = await createUser.mutateAsync(body);
    if (result.response?.status === 201) {
      setForm(EMPTY_FORM);
      return;
    }
    const status = result.response?.status;
    setError(status === 409 ? "That email is already in use." : "Could not create the account.");
  }

  async function toggleActive(user: User) {
    if (!user.id) return;
    await updateUser.mutateAsync({ id: user.id, body: { is_active: !user.is_active } });
  }

  async function toggleAdmin(user: User) {
    if (!user.id) return;
    await updateUser.mutateAsync({ id: user.id, body: { is_admin: !user.is_admin } });
  }

  async function saveDisplayName() {
    if (!editing || editing.display_name.trim().length === 0) return;
    const result = await updateUser.mutateAsync({
      id: editing.id,
      body: { display_name: editing.display_name.trim() }
    });
    if (result.response?.status === 200) setEditing(null);
  }

  const rows = users.data ?? [];

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6 text-zinc-950">
      <h1 className="text-xl font-semibold">Staff accounts</h1>

      <section className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Create account
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Role
            <input
              className="mt-1 block w-full rounded border border-zinc-200 bg-zinc-50 px-2 py-1 text-zinc-600"
              value="Doctor"
              disabled
            />
          </label>
          <label className="text-sm font-medium">
            Display name
            <input
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              value={form.display_name}
              onChange={(event) =>
                setForm((current) => ({ ...current, display_name: event.target.value }))
              }
            />
          </label>
          <label className="text-sm font-medium">
            Email
            <input
              type="email"
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              value={form.email}
              onChange={(event) =>
                setForm((current) => ({ ...current, email: event.target.value }))
              }
            />
          </label>
          <label className="text-sm font-medium">
            Temporary password
            <input
              type="text"
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              placeholder="≥ 8 characters"
              value={form.temp_password}
              onChange={(event) =>
                setForm((current) => ({ ...current, temp_password: event.target.value }))
              }
            />
            <span className="mt-1 block text-xs font-normal text-zinc-500">
              The user must change this on first sign-in.
            </span>
          </label>
          <label className="text-sm font-medium">
            Specialty <span className="font-normal text-zinc-400">(optional)</span>
            <input
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              value={form.specialty}
              onChange={(event) =>
                setForm((current) => ({ ...current, specialty: event.target.value }))
              }
            />
          </label>
        </div>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
        <div className="mt-4">
          <button
            type="button"
            className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={submitCreate}
            disabled={createUser.isPending}
          >
            Create account
          </button>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Center staff
        </h2>
        {rows.length === 0 ? (
          <p className="rounded border border-zinc-200 bg-white px-4 py-6 text-center text-sm text-zinc-500">
            No staff yet.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-200 overflow-hidden rounded-lg border border-zinc-200 bg-white">
            {rows.map((user) => (
              <li key={user.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  {editing?.id === user.id ? (
                    <input
                      className="w-full rounded border border-zinc-300 px-2 py-1 text-sm"
                      value={editing?.display_name ?? ""}
                      onChange={(event) =>
                        setEditing((current) =>
                          current ? { ...current, display_name: event.target.value } : current
                        )
                      }
                    />
                  ) : (
                    <span className="font-medium">{user.display_name}</span>
                  )}
                  <span className="ml-2 text-sm text-zinc-500">{user.email}</span>
                </div>
                <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs font-medium text-zinc-600">
                  {ROLE_LABELS[user.role ?? ""] ?? user.role}
                </span>
                {user.is_admin ? (
                  <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                    Admin
                  </span>
                ) : null}
                {user.must_change_password ? (
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                    <Abbr term="temp pwd" />
                  </span>
                ) : null}
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    user.is_active
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-zinc-100 text-zinc-500"
                  }`}
                >
                  {user.is_active ? "Active" : "Inactive"}
                </span>
                {user.role === "center_admin" ? null : editing?.id === user.id ? (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="rounded bg-emerald-700 px-3 py-1 text-sm font-medium text-white"
                      onClick={saveDisplayName}
                      disabled={updateUser.isPending}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="rounded px-3 py-1 text-sm font-medium text-zinc-600"
                      onClick={() => setEditing(null)}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="rounded border border-zinc-300 px-3 py-1 text-sm font-medium text-zinc-700"
                      onClick={() =>
                        setEditing({ id: user.id ?? "", display_name: user.display_name ?? "" })
                      }
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      className="rounded border border-zinc-300 px-3 py-1 text-sm font-medium text-zinc-700"
                      onClick={() => toggleActive(user)}
                      disabled={updateUser.isPending}
                    >
                      {user.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                    <button
                      type="button"
                      className="rounded border border-indigo-300 px-3 py-1 text-sm font-medium text-indigo-700"
                      onClick={() => toggleAdmin(user)}
                      disabled={updateUser.isPending}
                    >
                      {user.is_admin ? "Remove admin" : "Make admin"}
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
