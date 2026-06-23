import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import { useMemo, useState } from "react";

import { useAppointments } from "../api/hooks/appointments";
import { useDoctors } from "../api/hooks/availability";
import { BookingModal } from "../components/BookingModal";

const STATUS_COLORS: Record<string, string> = {
  scheduled: "#047857",
  completed: "#1d4ed8",
  cancelled: "#9ca3af",
  no_show: "#b91c1c"
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ReceptionCalendar() {
  const [date, setDate] = useState(today());
  const [doctorId, setDoctorId] = useState<string | null>(null);
  const [bookingOpen, setBookingOpen] = useState(false);

  const doctors = useDoctors();
  const appointments = useAppointments({});

  const events = useMemo(
    () =>
      (appointments.data ?? []).map((appt) => {
        const start = appt.starts_at ? new Date(appt.starts_at) : new Date();
        const end = new Date(start.getTime() + (appt.duration_minutes ?? 0) * 60_000);
        return {
          id: appt.id,
          title: `${appt.status ?? ""}`,
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
        <h1 className="text-xl font-semibold">Reception — day view</h1>
        <div className="flex items-end gap-2">
          <label className="text-sm font-medium">
            Date
            <input
              type="date"
              className="mt-1 block rounded border border-zinc-300 px-2 py-1"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <label className="text-sm font-medium">
            Doctor
            <select
              className="mt-1 block rounded border border-zinc-300 px-2 py-1"
              value={doctorId ?? ""}
              onChange={(event) => setDoctorId(event.target.value || null)}
            >
              <option value="">Select…</option>
              {(doctors.data ?? []).map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.display_name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            disabled={!doctorId}
            onClick={() => setBookingOpen(true)}
          >
            Book
          </button>
        </div>
      </div>

      <FullCalendar
        plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]}
        initialView="timeGridDay"
        initialDate={date}
        key={date}
        headerToolbar={{ left: "", center: "title", right: "" }}
        events={events}
        height="auto"
        nowIndicator
      />

      {doctorId ? (
        <BookingModal
          open={bookingOpen}
          onOpenChange={setBookingOpen}
          doctorId={doctorId}
          date={date}
          onBooked={() => appointments.refetch()}
        />
      ) : null}
    </main>
  );
}
