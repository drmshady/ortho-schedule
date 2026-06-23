import { useEffect, useMemo, useState } from "react";

import {
  useCreateException,
  useDeleteException,
  useDoctors,
  useExceptions
} from "../api/hooks/availability";
import { useClinics } from "../api/hooks/clinics";
import type { AvailabilityException } from "../api/generated";

// Four fixed daily sessions: 8–12, 1–4, 4–8, 8–12 (the night session ends a minute before
// midnight so it satisfies the end-after-start rule). Working hours are chosen per session.
const SESSIONS = [
  { id: "morning", label: "8–12", start: "08:00", end: "12:00" },
  { id: "afternoon", label: "1–4", start: "13:00", end: "16:00" },
  { id: "evening", label: "4–8", start: "16:00", end: "20:00" },
  { id: "night", label: "8–12", start: "20:00", end: "23:59" }
] as const;

type Session = (typeof SESSIONS)[number];

/** "08:00:00" / "08:00" -> "08:00" so API times compare cleanly against the session table. */
function hhmm(value: string | undefined): string {
  return (value ?? "").slice(0, 5);
}

function ymd(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseYmd(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month ?? 1) - 1, day ?? 1);
}

function addDays(value: string, days: number): string {
  const date = parseYmd(value);
  date.setDate(date.getDate() + days);
  return ymd(date);
}

/** Set each doctor's working hours per calendar date (schedules differ week to week). A session
 *  is stored as a date-specific `override` exception with an optional clinic assignment.
 *  Center-admins (and admin-flagged staff) manage any doctor; doctors manage only their own. */
export function WorkingHours() {
  const doctors = useDoctors();

  const [doctorId, setDoctorId] = useState<string | null>(null);
  const [weekStart, setWeekStart] = useState(() => ymd(new Date()));
  const [error, setError] = useState<string | null>(null);

  // Default to the first doctor in the center.
  useEffect(() => {
    if (doctorId) return;
    if ((doctors.data ?? []).length > 0) setDoctorId(doctors.data![0].id ?? null);
  }, [doctorId, doctors.data]);

  const exceptions = useExceptions(doctorId);
  const clinics = useClinics();
  const createException = useCreateException();
  const deleteException = useDeleteException();

  const activeClinics = useMemo(
    () => (clinics.data ?? []).filter((clinic) => clinic.is_active),
    [clinics.data]
  );

  // Date-specific scheduling uses `override` exceptions, which define the bookable hours for
  // that date in the resolver.
  const overrideRows = useMemo(
    () => (exceptions.data ?? []).filter((row) => row.kind === "override"),
    [exceptions.data]
  );
  const busy = createException.isPending || deleteException.isPending;
  const defaultClinic = activeClinics.length === 1 ? activeClinics[0].id ?? null : null;

  const weekDates = useMemo(
    () => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)),
    [weekStart]
  );

  function findOverride(date: string, session: Session): AvailabilityException | undefined {
    return overrideRows.find(
      (row) =>
        row.date === date &&
        hhmm(row.start_local) === session.start &&
        hhmm(row.end_local) === session.end
    );
  }

  async function createSession(date: string, session: Session, clinicId: string | null) {
    if (!doctorId) return;
    const result = await createException.mutateAsync({
      doctor_id: doctorId,
      clinic_id: clinicId ?? undefined,
      date,
      kind: "override",
      start_local: session.start,
      end_local: session.end
    });
    if (result.response?.status !== 201) setError("Could not update these hours. Try again.");
  }

  async function toggle(date: string, session: Session) {
    if (!doctorId) return;
    setError(null);
    const existing = findOverride(date, session);
    if (existing?.id) {
      deleteException.mutate(existing.id);
      return;
    }
    await createSession(date, session, defaultClinic);
  }

  // No update endpoint, so reassigning a session's clinic is delete-then-recreate.
  async function changeClinic(row: AvailabilityException, clinicId: string | null) {
    if (!row.id || !row.date) return;
    const session = SESSIONS.find(
      (item) => item.start === hhmm(row.start_local) && item.end === hhmm(row.end_local)
    );
    if (!session) return;
    setError(null);
    await deleteException.mutateAsync(row.id);
    await createSession(row.date, session, clinicId);
  }

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6 text-zinc-950">
      <h1 className="text-xl font-semibold">Working hours</h1>
      <p className="text-sm text-zinc-600">
        Set each doctor's bookable sessions per date — schedules can differ from week to week. Tap
        a session to turn it on, then assign the clinic for that session. Times are clinic-local.
      </p>

      <div className="flex flex-wrap items-end gap-4">
        <label className="block text-sm font-medium">
          Doctor
          <select
            className="mt-1 block w-64 rounded border border-zinc-300 px-2 py-1"
            value={doctorId ?? ""}
            onChange={(event) => setDoctorId(event.target.value || null)}
          >
            {(doctors.data ?? []).map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.display_name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-medium">
          Week starting
          <input
            type="date"
            className="mt-1 block rounded border border-zinc-300 px-2 py-1"
            value={weekStart}
            onChange={(event) => event.target.value && setWeekStart(event.target.value)}
          />
        </label>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Schedule for this week
        </h2>
        <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-zinc-500">
                <th className="px-3 py-2 text-left font-medium">Date</th>
                {SESSIONS.map((session) => (
                  <th key={session.id} className="px-3 py-2 text-center font-medium">
                    <div>{session.label}</div>
                    <div className="text-xs font-normal text-zinc-400">
                      {session.start}–{session.end}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {weekDates.map((date) => (
                <tr key={date} className="border-b border-zinc-100 last:border-0">
                  <td className="px-3 py-2 font-medium">
                    {parseYmd(date).toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric"
                    })}
                  </td>
                  {SESSIONS.map((session) => {
                    const row = findOverride(date, session);
                    const active = Boolean(row);
                    return (
                      <td key={session.id} className="px-2 py-2 align-top text-center">
                        <button
                          type="button"
                          aria-pressed={active}
                          onClick={() => toggle(date, session)}
                          disabled={busy || !doctorId}
                          className={`w-full rounded px-2 py-1 text-xs font-medium transition disabled:opacity-50 ${
                            active
                              ? "bg-emerald-600 text-white"
                              : "border border-zinc-300 text-zinc-500 hover:bg-zinc-50"
                          }`}
                        >
                          {active ? "Working" : "Off"}
                        </button>
                        {active && activeClinics.length > 0 ? (
                          <select
                            className="mt-1 w-full rounded border border-zinc-300 px-1 py-0.5 text-xs"
                            value={row?.clinic_id ?? ""}
                            disabled={busy}
                            onChange={(event) =>
                              row && changeClinic(row, event.target.value || null)
                            }
                          >
                            <option value="">No clinic</option>
                            {activeClinics.map((clinic) => (
                              <option key={clinic.id} value={clinic.id}>
                                Clinic {clinic.name}
                              </option>
                            ))}
                          </select>
                        ) : null}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
      </section>
    </main>
  );
}
