import * as Dialog from "@radix-ui/react-dialog";
import { useMemo, useState } from "react";

import { useDoctors } from "../api/hooks/availability";
import { usePatientSearch } from "../api/hooks/patients";
import { useDeclineRequest, useRequests } from "../api/hooks/requests";
import { BookingModal } from "../components/BookingModal";
import type { AppointmentRequest } from "../api/generated";

const URGENCY_STYLES: Record<string, string> = {
  urgent: "bg-red-100 text-red-800 border-red-200",
  soon: "bg-amber-100 text-amber-800 border-amber-200",
  routine: "bg-zinc-100 text-zinc-700 border-zinc-200"
};

const STATUS_FILTERS: Array<{ value: "pending" | "fulfilled" | "declined"; label: string }> = [
  { value: "pending", label: "Pending" },
  { value: "fulfilled", label: "Fulfilled" },
  { value: "declined", label: "Declined" }
];

function todayLocalDate(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

/** T067 + T068 — reception's pending-request queue, with urgency/overdue highlighting,
 *  fulfill-from-queue (reusing the booking modal), and decline-with-reason. */
export function RequestQueue() {
  const [statusFilter, setStatusFilter] = useState<"pending" | "fulfilled" | "declined">(
    "pending"
  );
  const requests = useRequests(statusFilter);
  const doctors = useDoctors();
  const patients = usePatientSearch("");
  const declineRequest = useDeclineRequest();

  const [fulfilling, setFulfilling] = useState<{ request: AppointmentRequest; date: string } | null>(
    null
  );
  const [declining, setDeclining] = useState<AppointmentRequest | null>(null);
  const [declineReason, setDeclineReason] = useState("");

  const doctorName = useMemo(() => {
    const map = new Map<string, string>();
    for (const doctor of doctors.data ?? []) {
      if (doctor.id) map.set(doctor.id, doctor.display_name ?? doctor.id);
    }
    return map;
  }, [doctors.data]);

  const patientName = useMemo(() => {
    const map = new Map<string, string>();
    for (const patient of patients.data ?? []) {
      if (patient.id) map.set(patient.id, patient.full_name ?? patient.id);
    }
    return map;
  }, [patients.data]);

  function openFulfill(request: AppointmentRequest) {
    setFulfilling({ request, date: request.preferred_from ?? todayLocalDate() });
  }

  async function submitDecline() {
    if (!declining?.id || declineReason.trim().length === 0) return;
    const result = await declineRequest.mutateAsync({
      id: declining.id,
      body: { decline_reason: declineReason.trim() }
    });
    if (result.response?.status === 200) {
      setDeclining(null);
      setDeclineReason("");
    }
  }

  const rows = requests.data ?? [];

  return (
    <main className="mx-auto max-w-4xl space-y-4 p-6 text-zinc-950">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold">Appointment requests</h1>
        <label className="text-sm font-medium">
          Status
          <select
            className="mt-1 block rounded border border-zinc-300 px-2 py-1"
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value as "pending" | "fulfilled" | "declined")
            }
          >
            {STATUS_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {rows.length === 0 ? (
        <p className="rounded border border-zinc-200 bg-white px-4 py-6 text-center text-sm text-zinc-500">
          No {statusFilter} requests.
        </p>
      ) : (
        <ul className="space-y-3">
          {rows.map((request) => (
            <li
              key={request.id}
              className={`rounded-lg border bg-white p-4 shadow-sm ${
                request.is_overdue ? "border-red-300 ring-1 ring-red-200" : "border-zinc-200"
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">
                  {request.patient_id ? (patientName.get(request.patient_id) ?? "Patient") : "Patient"}
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-xs font-medium uppercase ${
                    URGENCY_STYLES[request.urgency ?? "routine"]
                  }`}
                >
                  {request.urgency}
                </span>
                {request.is_overdue ? (
                  <span className="rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
                    Overdue
                  </span>
                ) : null}
                <span className="ml-auto text-sm text-zinc-500">
                  {request.doctor_id ? (doctorName.get(request.doctor_id) ?? "Doctor") : "Doctor"}
                </span>
              </div>

              <p className="mt-2 text-sm text-zinc-700">{request.reason}</p>
              <p className="mt-1 text-xs text-zinc-500">
                Expected {request.expected_duration_minutes} min
                {request.preferred_from || request.preferred_to
                  ? ` · preferred ${request.preferred_from ?? "…"} → ${request.preferred_to ?? "…"}`
                  : ""}
              </p>

              {request.status === "pending" ? (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="rounded bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white"
                    onClick={() => openFulfill(request)}
                  >
                    Fulfill
                  </button>
                  <button
                    type="button"
                    className="rounded border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700"
                    onClick={() => {
                      setDeclining(request);
                      setDeclineReason("");
                    }}
                  >
                    Decline
                  </button>
                </div>
              ) : request.status === "declined" ? (
                <p className="mt-3 text-sm text-zinc-500">Declined: {request.decline_reason}</p>
              ) : (
                <p className="mt-3 text-sm text-emerald-700">Fulfilled.</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {fulfilling ? (
        <div className="flex items-center gap-2 rounded border border-zinc-200 bg-zinc-50 p-3 text-sm">
          <label className="font-medium">
            Date
            <input
              type="date"
              className="ml-2 rounded border border-zinc-300 px-2 py-1"
              value={fulfilling.date}
              onChange={(event) =>
                setFulfilling((current) =>
                  current ? { ...current, date: event.target.value } : current
                )
              }
            />
          </label>
          <span className="text-zinc-500">Choose a slot in the booking dialog →</span>
        </div>
      ) : null}

      {fulfilling ? (
        <BookingModal
          open={Boolean(fulfilling)}
          onOpenChange={(open) => {
            if (!open) setFulfilling(null);
          }}
          doctorId={fulfilling.request.doctor_id ?? ""}
          date={fulfilling.date}
          fulfillRequestId={fulfilling.request.id ?? undefined}
          lockedPatientId={fulfilling.request.patient_id ?? undefined}
          lockedPatientLabel={
            fulfilling.request.patient_id
              ? patientName.get(fulfilling.request.patient_id)
              : undefined
          }
          initialDuration={fulfilling.request.expected_duration_minutes ?? 30}
          onBooked={() => setFulfilling(null)}
        />
      ) : null}

      <Dialog.Root
        open={Boolean(declining)}
        onOpenChange={(open) => {
          if (!open) setDeclining(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40" />
          <Dialog.Content className="fixed left-1/2 top-1/2 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-lg bg-white p-6 text-zinc-950 shadow-xl">
            <Dialog.Title className="text-lg font-semibold">Decline request</Dialog.Title>
            <Dialog.Description className="text-sm text-zinc-600">
              The requesting doctor is notified with your reason.
            </Dialog.Description>
            <textarea
              className="w-full rounded border border-zinc-300 px-3 py-2 text-sm"
              rows={3}
              placeholder="Reason for declining"
              value={declineReason}
              onChange={(event) => setDeclineReason(event.target.value)}
            />
            <div className="flex justify-end gap-2">
              <Dialog.Close asChild>
                <button type="button" className="rounded px-4 py-2 text-sm font-medium text-zinc-700">
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="button"
                className="rounded bg-red-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                onClick={submitDecline}
                disabled={declineReason.trim().length === 0 || declineRequest.isPending}
              >
                Decline
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </main>
  );
}
