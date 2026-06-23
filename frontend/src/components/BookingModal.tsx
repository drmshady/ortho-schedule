import * as Dialog from "@radix-ui/react-dialog";
import { useMemo, useState } from "react";

import { usePatientSearch } from "../api/hooks/patients";
import { useSlots } from "../api/hooks/availability";
import { useClinics } from "../api/hooks/clinics";
import { useCreateAppointment } from "../api/hooks/appointments";
import { useFulfillRequest } from "../api/hooks/requests";
import { Abbr } from "./Abbr";

const DURATION_OPTIONS = [15, 30, 45, 60];
const STEP_MINUTES = 15;

type BookingModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  doctorId: string;
  /** YYYY-MM-DD in the center's local date. */
  date: string;
  sourceRequestId?: string;
  /**
   * When set, the booking fulfills this appointment request (routes through the fulfill
   * endpoint, which also marks the request fulfilled and notifies the doctor). The patient is
   * then locked to the request's patient.
   */
  fulfillRequestId?: string;
  lockedPatientId?: string;
  lockedPatientLabel?: string;
  initialDuration?: number;
  onBooked?: () => void;
};

/** Build the discrete grid-aligned start times that fit `duration` inside the bookable intervals. */
function candidateStarts(
  intervals: Array<{ start?: string; end?: string }>,
  durationMinutes: number
): string[] {
  const starts: string[] = [];
  for (const interval of intervals) {
    if (!interval.start || !interval.end) continue;
    const end = new Date(interval.end).getTime();
    let cursor = new Date(interval.start).getTime();
    while (cursor + durationMinutes * 60_000 <= end) {
      starts.push(new Date(cursor).toISOString());
      cursor += STEP_MINUTES * 60_000;
    }
  }
  return starts;
}

export function BookingModal({
  open,
  onOpenChange,
  doctorId,
  date,
  sourceRequestId,
  fulfillRequestId,
  lockedPatientId,
  lockedPatientLabel,
  initialDuration,
  onBooked
}: BookingModalProps) {
  const [patientQuery, setPatientQuery] = useState("");
  const [patientId, setPatientId] = useState<string | null>(lockedPatientId ?? null);
  const [patientMode, setPatientMode] = useState<"existing" | "walkin">("existing");
  const [walkInName, setWalkInName] = useState("");
  const [walkInId, setWalkInId] = useState("");
  const [clinicId, setClinicId] = useState<string>("");
  const [duration, setDuration] = useState(initialDuration ?? 30);
  const [startsAt, setStartsAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [needsConflictConfirm, setNeedsConflictConfirm] = useState(false);

  const patients = usePatientSearch(patientQuery);
  const clinics = useClinics();
  const activeClinics = (clinics.data ?? []).filter((clinic) => clinic.is_active);
  const slots = useSlots(doctorId, date);
  const createAppointment = useCreateAppointment();
  const fulfillRequest = useFulfillRequest();
  const isFulfilling = Boolean(fulfillRequestId);
  const effectivePatientId = lockedPatientId ?? patientId;

  const options = useMemo(
    () => candidateStarts(slots.data ?? [], duration),
    [slots.data, duration]
  );

  const isWalkIn = !lockedPatientId && patientMode === "walkin";
  const hasWalkIn = walkInName.trim().length > 0 && walkInId.trim().length > 0;

  async function submit(confirmPatientConflict: boolean) {
    if (!startsAt) {
      setError("Select an open slot.");
      return;
    }
    if (isWalkIn ? !hasWalkIn : !effectivePatientId) {
      setError(isWalkIn ? "Enter the patient's name and ID." : "Select a patient.");
      return;
    }
    setError(null);
    const body = {
      doctor_id: doctorId,
      patient_id: isWalkIn ? undefined : effectivePatientId ?? undefined,
      patient_name: isWalkIn ? walkInName.trim() : undefined,
      patient_clinic_identifier: isWalkIn ? walkInId.trim() : undefined,
      clinic_id: clinicId || undefined,
      starts_at: startsAt,
      duration_minutes: duration,
      source_request_id: sourceRequestId,
      confirm_patient_conflict: confirmPatientConflict
    };
    const result =
      isFulfilling && fulfillRequestId
        ? await fulfillRequest.mutateAsync({ id: fulfillRequestId, body })
        : await createAppointment.mutateAsync(body);
    if (result.response?.status === 201) {
      onBooked?.();
      onOpenChange(false);
      return;
    }
    const code = (result.error as { code?: string } | undefined)?.code;
    if (code === "patient_conflict") {
      setNeedsConflictConfirm(true);
      setError("This patient already has an overlapping appointment.");
    } else if (code === "double_booking") {
      setError("That slot was just taken for this doctor. Pick another.");
    } else if (code === "clinic_double_booking") {
      setError("That clinic is already in use at this time. Pick another clinic or slot.");
    } else if (code === "inactive_clinic") {
      setError("The selected clinic is inactive.");
    } else if (code === "outside_availability") {
      setError("That time is outside the doctor's availability.");
    } else if (code === "off_grid") {
      setError("That time is not aligned to the booking grid.");
    } else if (code === "invalid_transition") {
      setError("This request was already fulfilled or declined.");
    } else {
      setError("Could not book the appointment. Please try again.");
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-lg bg-white p-6 text-zinc-950 shadow-xl">
          <Dialog.Title className="text-lg font-semibold">
            {isFulfilling ? "Fulfill request" : "Book appointment"}
          </Dialog.Title>
          <Dialog.Description className="text-sm text-zinc-600">
            Pick {lockedPatientId ? "an open slot" : "a patient and an open slot"}. Times shown in
            clinic-local time (stored as <Abbr term="UTC" />).
          </Dialog.Description>

          {lockedPatientId ? (
            <div className="rounded border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm">
              <span className="font-medium">Patient:</span>{" "}
              {lockedPatientLabel ?? "From request"}
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex gap-2 text-sm">
                <button
                  type="button"
                  onClick={() => setPatientMode("existing")}
                  className={`rounded px-3 py-1 font-medium ${
                    patientMode === "existing"
                      ? "bg-emerald-700 text-white"
                      : "border border-zinc-300 text-zinc-700"
                  }`}
                >
                  Existing patient
                </button>
                <button
                  type="button"
                  onClick={() => setPatientMode("walkin")}
                  className={`rounded px-3 py-1 font-medium ${
                    patientMode === "walkin"
                      ? "bg-emerald-700 text-white"
                      : "border border-zinc-300 text-zinc-700"
                  }`}
                >
                  New / walk-in
                </button>
              </div>

              {patientMode === "existing" ? (
                <div className="space-y-1">
                  <input
                    id="patient-search"
                    className="w-full rounded border border-zinc-300 px-3 py-2"
                    placeholder="Search name or ID"
                    value={patientQuery}
                    onChange={(event) => setPatientQuery(event.target.value)}
                  />
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
              ) : (
                <div className="space-y-2">
                  <input
                    className="w-full rounded border border-zinc-300 px-3 py-2"
                    placeholder="Full name"
                    value={walkInName}
                    onChange={(event) => setWalkInName(event.target.value)}
                  />
                  <input
                    className="w-full rounded border border-zinc-300 px-3 py-2"
                    placeholder="Patient ID"
                    value={walkInId}
                    onChange={(event) => setWalkInId(event.target.value)}
                  />
                  <p className="text-xs text-zinc-500">
                    No need to pre-register — the patient is created on booking, or matched if the
                    ID already exists.
                  </p>
                </div>
              )}
            </div>
          )}

          {activeClinics.length > 0 ? (
            <label className="block text-sm font-medium">
              Clinic <span className="font-normal text-zinc-400">(working unit)</span>
              <select
                className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
                value={clinicId}
                onChange={(event) => setClinicId(event.target.value)}
              >
                <option value="">No specific clinic</option>
                {activeClinics.map((clinic) => (
                  <option key={clinic.id} value={clinic.id}>
                    Clinic {clinic.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div className="flex gap-3">
            <label className="block flex-1 text-sm font-medium">
              Duration (min)
              <select
                className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
                value={duration}
                onChange={(event) => {
                  setDuration(Number(event.target.value));
                  setStartsAt(null);
                }}
              >
                {DURATION_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="block flex-1 text-sm font-medium">
              Start
              <select
                className="mt-1 w-full rounded border border-zinc-300 px-3 py-2"
                value={startsAt ?? ""}
                onChange={(event) => setStartsAt(event.target.value || null)}
              >
                <option value="">Select…</option>
                {options.map((iso) => (
                  <option key={iso} value={iso}>
                    {new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {options.length === 0 ? (
            <p className="text-sm text-amber-700">No open slots for this doctor on {date}.</p>
          ) : null}
          {error ? <p className="text-sm text-red-700">{error}</p> : null}

          <div className="flex justify-end gap-2">
            <Dialog.Close asChild>
              <button type="button" className="rounded px-4 py-2 text-sm font-medium text-zinc-700">
                Cancel
              </button>
            </Dialog.Close>
            {needsConflictConfirm ? (
              <button
                type="button"
                className="rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white"
                onClick={() => submit(true)}
              >
                Book anyway
              </button>
            ) : (
              <button
                type="button"
                className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white"
                onClick={() => submit(false)}
                disabled={createAppointment.isPending || fulfillRequest.isPending}
              >
                Confirm
              </button>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
