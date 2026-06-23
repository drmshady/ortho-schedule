import { useState } from "react";

import {
  useCenters,
  useCreateCenter,
  useSetCenterStatus,
  useUpdateCenterTimezone
} from "../api/hooks/centers";
import { Abbr } from "../components/Abbr";
import type { Center, CenterCreate } from "../api/generated";

// Common time zones; Saudi Arabia (Asia/Riyadh) is the default for new centers.
const TIMEZONES = [
  "Asia/Riyadh",
  "Africa/Cairo",
  "Asia/Dubai",
  "Asia/Kuwait",
  "Asia/Qatar",
  "Asia/Bahrain",
  "Asia/Baghdad",
  "Europe/Istanbul",
  "Europe/London",
  "America/New_York",
  "UTC"
];

// The first admin can be a dedicated center admin, or a doctor/receptionist who is also
// granted admin privileges (keeps their working role).
const ADMIN_ROLES = [
  { value: "center_admin", label: "Center admin (dedicated)" },
  { value: "doctor", label: "Doctor (with admin rights)" },
  { value: "reception", label: "Receptionist (with admin rights)" }
] as const;

const EMPTY_FORM = {
  name: "",
  timezone: "Asia/Riyadh",
  grid_minutes: 15,
  admin_email: "",
  admin_temp_password: "",
  admin_role: "center_admin"
};

/** T083 — platform super-admin center provisioning (US4, FR-023..FR-026): list every center,
 *  create a center together with its first center-admin (issued a temporary password), and
 *  suspend/reactivate centers. The super-admin is the only cross-center role. */
export function SuperAdminCenters() {
  const centers = useCenters();
  const createCenter = useCreateCenter();
  const setStatus = useSetCenterStatus();
  const updateTimezone = useUpdateCenterTimezone();

  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [editingTz, setEditingTz] = useState<{ id: string; timezone: string } | null>(null);

  async function submitCreate() {
    if (
      !form.name.trim() ||
      !form.timezone.trim() ||
      !form.admin_email.trim() ||
      form.admin_temp_password.length < 8
    ) {
      setError(
        "Center name, time zone, first-admin email, and a temporary password (≥8 characters) are required."
      );
      return;
    }
    setError(null);
    const body: CenterCreate = {
      name: form.name.trim(),
      timezone: form.timezone.trim(),
      grid_minutes: form.grid_minutes,
      admin_email: form.admin_email.trim(),
      admin_temp_password: form.admin_temp_password,
      admin_role: form.admin_role as CenterCreate["admin_role"]
    };
    const result = await createCenter.mutateAsync(body);
    if (result.response?.status === 201) {
      setForm(EMPTY_FORM);
      return;
    }
    const status = result.response?.status;
    setError(
      status === 409 ? "That admin email is already in use." : "Could not create the center."
    );
  }

  async function toggleStatus(center: Center) {
    if (!center.id) return;
    const next = center.status === "active" ? "suspended" : "active";
    await setStatus.mutateAsync({ id: center.id, status: next });
  }

  async function saveTimezone() {
    if (!editingTz || !editingTz.timezone.trim()) return;
    const result = await updateTimezone.mutateAsync({
      id: editingTz.id,
      timezone: editingTz.timezone
    });
    if (result.response?.status === 200) setEditingTz(null);
  }

  const rows = centers.data ?? [];

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6 text-zinc-950">
      <h1 className="text-xl font-semibold">Centers</h1>

      <section className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Create center
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Center name
            <input
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
            />
          </label>
          <label className="text-sm font-medium">
            Time zone (<Abbr term="tz" />)
            <select
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              value={form.timezone}
              onChange={(event) =>
                setForm((current) => ({ ...current, timezone: event.target.value }))
              }
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Grid (minutes)
            <input
              type="number"
              min={1}
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              value={form.grid_minutes}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  grid_minutes: Number(event.target.value) || 0
                }))
              }
            />
          </label>
          <label className="text-sm font-medium">
            First admin email
            <input
              type="email"
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              value={form.admin_email}
              onChange={(event) =>
                setForm((current) => ({ ...current, admin_email: event.target.value }))
              }
            />
          </label>
          <label className="text-sm font-medium">
            Admin temporary password
            <input
              type="text"
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              placeholder="≥ 8 characters"
              value={form.admin_temp_password}
              onChange={(event) =>
                setForm((current) => ({ ...current, admin_temp_password: event.target.value }))
              }
            />
            <span className="mt-1 block text-xs font-normal text-zinc-500">
              The admin must change this on first sign-in.
            </span>
          </label>
          <label className="text-sm font-medium">
            First admin role
            <select
              className="mt-1 block w-full rounded border border-zinc-300 px-2 py-1"
              value={form.admin_role}
              onChange={(event) =>
                setForm((current) => ({ ...current, admin_role: event.target.value }))
              }
            >
              {ADMIN_ROLES.map((role) => (
                <option key={role.value} value={role.value}>
                  {role.label}
                </option>
              ))}
            </select>
            <span className="mt-1 block text-xs font-normal text-zinc-500">
              A doctor or receptionist keeps their role and also gains admin rights.
            </span>
          </label>
        </div>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
        <div className="mt-4">
          <button
            type="button"
            className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={submitCreate}
            disabled={createCenter.isPending}
          >
            Create center
          </button>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          All centers
        </h2>
        {rows.length === 0 ? (
          <p className="rounded border border-zinc-200 bg-white px-4 py-6 text-center text-sm text-zinc-500">
            No centers yet.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-200 overflow-hidden rounded-lg border border-zinc-200 bg-white">
            {rows.map((center) => (
              <li key={center.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <span className="font-medium">{center.name}</span>
                  {editingTz?.id === center.id ? (
                    <select
                      className="ml-2 rounded border border-zinc-300 px-2 py-1 text-sm"
                      value={editingTz?.timezone ?? ""}
                      onChange={(event) =>
                        setEditingTz((current) =>
                          current ? { ...current, timezone: event.target.value } : current
                        )
                      }
                    >
                      {[...new Set([center.timezone ?? "", ...TIMEZONES])]
                        .filter(Boolean)
                        .map((tz) => (
                          <option key={tz} value={tz}>
                            {tz}
                          </option>
                        ))}
                    </select>
                  ) : (
                    <span className="ml-2 text-sm text-zinc-500">{center.timezone}</span>
                  )}
                </div>
                <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs font-medium text-zinc-600">
                  {center.grid_minutes}-min grid
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    center.status === "active"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-amber-50 text-amber-700"
                  }`}
                >
                  {center.status === "active" ? "Active" : "Suspended"}
                </span>
                {editingTz?.id === center.id ? (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="rounded bg-emerald-700 px-3 py-1 text-sm font-medium text-white"
                      onClick={saveTimezone}
                      disabled={updateTimezone.isPending}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="rounded px-3 py-1 text-sm font-medium text-zinc-600"
                      onClick={() => setEditingTz(null)}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="rounded border border-zinc-300 px-3 py-1 text-sm font-medium text-zinc-700"
                    onClick={() =>
                      setEditingTz({ id: center.id ?? "", timezone: center.timezone ?? "Asia/Riyadh" })
                    }
                  >
                    Time zone
                  </button>
                )}
                <button
                  type="button"
                  className="rounded border border-zinc-300 px-3 py-1 text-sm font-medium text-zinc-700"
                  onClick={() => toggleStatus(center)}
                  disabled={setStatus.isPending}
                >
                  {center.status === "active" ? "Suspend" : "Reactivate"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
