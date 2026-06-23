import dayGridPlugin from "@fullcalendar/daygrid";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useMemo, useState } from "react";

import { useAppointments } from "../api/hooks/appointments";
import { useDoctors } from "../api/hooks/availability";
import { useAuth } from "../lib/auth";

const STATUS_COLORS: Record<string, string> = {
  scheduled: "#047857",
  completed: "#1d4ed8",
  cancelled: "#9ca3af",
  no_show: "#b91c1c"
};

export function DoctorSchedule() {
  const { session } = useAuth();
  const doctors = useDoctors();
  const isDoctor = session?.role === "doctor";
  const [selectedDoctor, setSelectedDoctor] = useState<string | null>(
    isDoctor ? (session?.user_id ?? null) : null
  );
  const doctorId = isDoctor ? (session?.user_id ?? null) : selectedDoctor;

  const appointments = useAppointments({ doctorId });

  const events = useMemo(
    () =>
      (appointments.data ?? []).map((appt) => {
        const start = appt.starts_at ? new Date(appt.starts_at) : new Date();
        const end = new Date(start.getTime() + (appt.duration_minutes ?? 0) * 60_000);
        return {
          id: appt.id,
          title: appt.status ?? "",
          start: start.toISOString(),
          end: end.toISOString(),
          backgroundColor: STATUS_COLORS[appt.status ?? "scheduled"],
          borderColor: STATUS_COLORS[appt.status ?? "scheduled"]
        };
      }),
    [appointments.data]
  );

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-6 text-zinc-950">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold">Doctor schedule</h1>
        {!isDoctor ? (
          <label className="text-sm font-medium">
            Doctor
            <select
              className="mt-1 block rounded border border-zinc-300 px-2 py-1"
              value={selectedDoctor ?? ""}
              onChange={(event) => setSelectedDoctor(event.target.value || null)}
            >
              <option value="">Select…</option>
              {(doctors.data ?? []).map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.display_name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      <FullCalendar
        plugins={[timeGridPlugin, dayGridPlugin]}
        initialView="timeGridWeek"
        headerToolbar={{ left: "prev,next today", center: "title", right: "timeGridWeek,timeGridDay" }}
        events={events}
        height="auto"
        nowIndicator
      />
    </main>
  );
}
