import { useMemo, useState } from "react";

import { usePatientSearch } from "../api/hooks/patients";
import { useCreateRequest } from "../api/hooks/requests";
import { Abbr } from "../components/Abbr";
import type { AppointmentRequestCreate } from "../api/generated";

const DURATION_OPTIONS = [15, 30, 45, 60];
const URGENCY_OPTIONS: Array<{ value: "routine" | "soon" | "urgent"; label: string }> = [
  { value: "routine", label: "Routine" },
  { value: "soon", label: "Soon" },
  { value: "urgent", label: "Urgent" }
];

/** T066 — a doctor submits an appointment request to reception (FR-014). */
export function DoctorRequestForm() {
  const [patientQuery, setPatientQuery] = useState("");
  const [patientId, setPatientId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [urgency, setUrgency] = useState<"routine" | "soon" | "urgent">("routine");
  const [duration, setDuration] = useState(30);
  const [preferredFrom, setPreferredFrom] = useState("");
  const [preferredTo, setPreferredTo] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const patients = usePatientSearch(patientQuery);
  const createRequest = useCreateRequest();

  const selectedPatient = useMemo(
    () => (patients.data ?? []).find((patient) => patient.id === patientId) ?? null,
    [patients.data, patientId]
  );

  async function submit() {
    if (!patientId) {
      setError("Select a patient.");
      return;
    }
    setError(null);
    const body: AppointmentRequestCreate = {
      patient_id: patientId,
      reason: reason.trim() ? reason.trim() : undefined,
      urgency,
      expected_duration_minutes: duration,
      preferred_from: preferredFrom || undefined,
      preferred_to: preferredTo || undefined,
      notes: notes.trim() ? notes.trim() : undefined
    };
    const result = await createRequest.mutateAsync(body);
    if (result.response?.status === 201) {
      setSubmitted(true);
      setPatientId(null);
      setPatientQuery("");
      setReason("");
      setNotes("");
      setPreferredFrom("");
      setPreferredTo("");
      return;
    }
    setError("Could not submit the request. Please try again.");
  }

  return (
    <main className="mx-auto max-w-2xl space-y-5 p-6 text-zinc-950">
      <h1 className="text-xl font-semibold">Request an appointment</h1>
      <p className="text-sm text-zinc-600">
        Hand a request to reception, who will book a concrete slot. Patient details stay{" "}
        <Abbr term="PHI" />-protected; you will be notified when it is fulfilled or declined.
      </p>

      {submitted ? (
        <p className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          Request submitted. Reception will follow up.
        </p>
      ) : null}

      <div className="space-y-1">
        <label className="block text-sm font-medium" htmlFor="patient-search">
          Patient
        </label>
        <input
          id="patient-search"
          className="w-full rounded border border-zinc-300 px-3 py-2"
          placeholder="Search name or ID"
          value={patientQuery}
          onChange={(event) => setPatientQuery(event.target.value)}
        />
        {selectedPatient ? (
          <p className="text-sm text-emerald-700">Selected: {selectedPatient.full_name}</p>
        ) : null}
        <ul className="max-h-32 overflow-auto rounded border border-zinc-200">
          {(patients.data ?? []).map((patient) => (
            <li key={patient.id}>
              <button
                type="button"
                onClick={() => setPatientId(patient.id ?? null)}
                className={`flex w-full justify-between px-3 py-1 text-left text-sm hover:bg-zinc-100 ${
                  patientId === patient.id ? "bg-emerald-50 font-medium" : ""
                }`}
              >
                <span>{patient.full_name}</span>
                <span className="text-zinc-500">{patient.clinic_identifier}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <label className="block text-sm font-medium">
        Reason / visit type <span className="font-normal text-zinc-400">(optional)</span>
        <input
          className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>

      <div className="flex flex-wrap gap-4">
        <label className="block text-sm font-medium">
          Urgency
          <select
            className="mt-1 block rounded border border-zinc-300 px-3 py-2"
            value={urgency}
            onChange={(event) => setUrgency(event.target.value as typeof urgency)}
          >
            {URGENCY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Expected duration (min)
          <select
            className="mt-1 block rounded border border-zinc-300 px-3 py-2"
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
          >
            {DURATION_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="block text-sm font-medium">
          Preferred from
          <input
            type="date"
            className="mt-1 block rounded border border-zinc-300 px-3 py-2"
            value={preferredFrom}
            onChange={(event) => setPreferredFrom(event.target.value)}
          />
        </label>
        <label className="block text-sm font-medium">
          Preferred to
          <input
            type="date"
            className="mt-1 block rounded border border-zinc-300 px-3 py-2"
            value={preferredTo}
            onChange={(event) => setPreferredTo(event.target.value)}
          />
        </label>
      </div>

      <label className="block text-sm font-medium">
        Notes (optional)
        <textarea
          className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
          rows={3}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </label>

      {error ? <p className="text-sm text-red-700">{error}</p> : null}

      <button
        type="button"
        className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white"
        onClick={submit}
        disabled={createRequest.isPending}
      >
        Submit request
      </button>
    </main>
  );
}
