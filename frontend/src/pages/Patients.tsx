import { FormEvent, useState } from "react";

import { usePatientSearch, useCreatePatient } from "../api/hooks/patients";
import { Abbr } from "../components/Abbr";
import type { Patient } from "../api/generated";

export function Patients() {
  const [query, setQuery] = useState("");
  const [form, setForm] = useState({ full_name: "", clinic_identifier: "" });
  const [duplicates, setDuplicates] = useState<Patient[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const results = usePatientSearch(query);
  const createPatient = useCreatePatient();

  async function register(event: FormEvent<HTMLFormElement>, confirm: boolean) {
    event.preventDefault();
    setMessage(null);
    const result = await createPatient.mutateAsync({
      full_name: form.full_name,
      clinic_identifier: form.clinic_identifier.trim() || undefined,
      confirm_possible_duplicate: confirm
    });
    if (result.response?.status === 201) {
      setForm({ full_name: "", clinic_identifier: "" });
      setDuplicates(null);
      setMessage("Patient registered.");
      return;
    }
    if (result.response?.status === 409) {
      const warning = result.error as { candidates?: Patient[] } | undefined;
      setDuplicates(warning?.candidates ?? []);
    }
  }

  return (
    <main className="mx-auto max-w-3xl space-y-8 p-6 text-zinc-950">
      <h1 className="text-xl font-semibold">Patients</h1>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-zinc-700">Find a patient</h2>
        <input
          className="w-full rounded border border-zinc-300 px-3 py-2"
          placeholder="Search by name or ID"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {(results.data ?? []).map((patient) => (
            <li key={patient.id} className="flex justify-between px-3 py-2 text-sm">
              <span>{patient.full_name}</span>
              <span className="text-zinc-500">{patient.clinic_identifier}</span>
            </li>
          ))}
          {results.data?.length === 0 ? (
            <li className="px-3 py-2 text-sm text-zinc-500">No patients found.</li>
          ) : null}
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-zinc-700">
          Register a patient — <Abbr term="PHI" /> is minimized and audited
        </h2>
        <form className="space-y-3" onSubmit={(event) => register(event, false)}>
          <input
            className="w-full rounded border border-zinc-300 px-3 py-2"
            placeholder="Full name"
            value={form.full_name}
            onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
            required
          />
          <input
            className="w-full rounded border border-zinc-300 px-3 py-2"
            placeholder="Patient ID (auto-assigned if left blank)"
            value={form.clinic_identifier}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, clinic_identifier: event.target.value }))
            }
          />
          {duplicates ? (
            <div className="space-y-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm">
              <p className="font-medium text-amber-800">
                A possible duplicate already exists in this center:
              </p>
              <ul className="list-disc pl-5">
                {duplicates.map((patient) => (
                  <li key={patient.id}>
                    {patient.full_name} — {patient.clinic_identifier}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="rounded bg-amber-600 px-4 py-2 font-medium text-white"
                onClick={(event) =>
                  register(event as unknown as FormEvent<HTMLFormElement>, true)
                }
              >
                Register anyway
              </button>
            </div>
          ) : (
            <button
              type="submit"
              className="rounded bg-emerald-700 px-4 py-2 font-medium text-white"
              disabled={createPatient.isPending}
            >
              Register
            </button>
          )}
          {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
        </form>
      </section>
    </main>
  );
}
