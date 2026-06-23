import { useState } from "react";

import {
  useClinics,
  useCreateClinic,
  useDeleteClinic,
  useUpdateClinic
} from "../api/hooks/clinics";
import type { Clinic } from "../api/generated";

/** Center-admin management of clinics (numbered working units / rooms).
 *  Add, rename, activate/deactivate, and remove. Each clinic is center-scoped server-side. */
export function AdminClinics() {
  const clinics = useClinics();
  const createClinic = useCreateClinic();
  const updateClinic = useUpdateClinic();
  const deleteClinic = useDeleteClinic();

  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (!name.trim()) {
      setError("Enter a clinic number or name.");
      return;
    }
    setError(null);
    const result = await createClinic.mutateAsync({ name: name.trim() });
    if (result.response?.status === 201) {
      setName("");
      return;
    }
    setError(
      result.response?.status === 409
        ? "A clinic with that name already exists."
        : "Could not add the clinic."
    );
  }

  async function remove(clinic: Clinic) {
    if (!clinic.id) return;
    const result = await deleteClinic.mutateAsync(clinic.id);
    if (result.response?.status === 409) {
      // Has appointments — deactivate instead of hard delete.
      await updateClinic.mutateAsync({ id: clinic.id, body: { is_active: false } });
    }
  }

  async function toggleActive(clinic: Clinic) {
    if (!clinic.id) return;
    await updateClinic.mutateAsync({ id: clinic.id, body: { is_active: !clinic.is_active } });
  }

  const rows = clinics.data ?? [];

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6 text-zinc-950">
      <h1 className="text-xl font-semibold">Clinics</h1>
      <p className="text-sm text-zinc-600">
        Clinics are the working units (rooms) in this center, usually named by number. Appointments
        can be assigned to a clinic, and one clinic cannot hold two overlapping appointments.
      </p>

      <section className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Add clinic</h2>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-sm font-medium">
            Clinic number / name
            <input
              className="mt-1 block w-48 rounded border border-zinc-300 px-2 py-1"
              placeholder="e.g. 1"
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void add();
              }}
            />
          </label>
          <button
            type="button"
            className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={add}
            disabled={createClinic.isPending}
          >
            Add
          </button>
        </div>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Clinics in this center
        </h2>
        {rows.length === 0 ? (
          <p className="rounded border border-zinc-200 bg-white px-4 py-6 text-center text-sm text-zinc-500">
            No clinics yet.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-200 overflow-hidden rounded-lg border border-zinc-200 bg-white">
            {rows.map((clinic) => (
              <li key={clinic.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <span className="min-w-0 flex-1 font-medium">Clinic {clinic.name}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    clinic.is_active
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-zinc-100 text-zinc-500"
                  }`}
                >
                  {clinic.is_active ? "Active" : "Inactive"}
                </span>
                <button
                  type="button"
                  className="rounded border border-zinc-300 px-3 py-1 text-sm font-medium text-zinc-700"
                  onClick={() => toggleActive(clinic)}
                  disabled={updateClinic.isPending}
                >
                  {clinic.is_active ? "Deactivate" : "Reactivate"}
                </button>
                <button
                  type="button"
                  className="rounded border border-red-200 px-3 py-1 text-sm font-medium text-red-700"
                  onClick={() => remove(clinic)}
                  disabled={deleteClinic.isPending || updateClinic.isPending}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-zinc-500">
          Removing a clinic that already has appointments deactivates it instead of deleting, to
          preserve history.
        </p>
      </section>
    </main>
  );
}
