import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { NotificationBell } from "./components/NotificationBell";
import { AuthProvider, RequireAuth, useAuth } from "./lib/auth";
import { queryClient } from "./lib/query";
import { AdminClinics } from "./pages/AdminClinics";
import { AdminStaff } from "./pages/AdminStaff";
import { ChangePassword } from "./pages/ChangePassword";
import { DoctorRequestForm } from "./pages/DoctorRequestForm";
import { DoctorSchedule } from "./pages/DoctorSchedule";
import { Login } from "./pages/Login";
import { Patients } from "./pages/Patients";
import { ReceptionCalendar } from "./pages/ReceptionCalendar";
import { RequestQueue } from "./pages/RequestQueue";
import { SuperAdminCenters } from "./pages/SuperAdminCenters";
import { WorkingHours } from "./pages/WorkingHours";

function Nav() {
  const { session, logout } = useAuth();
  if (!session) return null;
  const role = session.role;
  return (
    <nav className="flex items-center gap-4 border-b border-zinc-200 bg-white px-6 py-3 text-sm">
      <span className="font-semibold">Clinic scheduling</span>
      {(role === "reception" || role === "center_admin") && <Link to="/">Calendar</Link>}
      {(role === "reception" || role === "center_admin") && <Link to="/patients">Patients</Link>}
      {(role === "reception" || role === "center_admin") && <Link to="/requests">Requests</Link>}
      {role === "doctor" && <Link to="/requests/new">Request appointment</Link>}
      {role === "center_admin" && <Link to="/staff">Staff</Link>}
      {role === "center_admin" && <Link to="/clinics">Clinics</Link>}
      {role === "center_admin" && <Link to="/working-hours">Working hours</Link>}
      {role === "super_admin" && <Link to="/centers">Centers</Link>}
      {role !== "super_admin" && <Link to="/schedule">Doctor schedule</Link>}
      <div className="ml-auto flex items-center gap-4">
        <NotificationBell />
        <button type="button" className="text-zinc-600" onClick={() => logout()}>
          Sign out
        </button>
      </div>
    </nav>
  );
}

function Home() {
  const { session } = useAuth();
  if (session?.role === "super_admin") return <SuperAdminCenters />;
  if (session?.role === "doctor") return <DoctorSchedule />;
  return <ReceptionCalendar />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              element={
                <>
                  <Nav />
                  <RequireAuth />
                </>
              }
            >
              <Route path="/" element={<Home />} />
              <Route path="/change-password" element={<ChangePassword />} />
              <Route
                element={<RequireAuth roles={["reception", "center_admin"]} />}
              >
                <Route path="/patients" element={<Patients />} />
                <Route path="/requests" element={<RequestQueue />} />
              </Route>
              <Route element={<RequireAuth roles={["doctor"]} />}>
                <Route path="/requests/new" element={<DoctorRequestForm />} />
              </Route>
              <Route element={<RequireAuth roles={["center_admin"]} />}>
                <Route path="/staff" element={<AdminStaff />} />
                <Route path="/clinics" element={<AdminClinics />} />
                <Route path="/working-hours" element={<WorkingHours />} />
              </Route>
              <Route element={<RequireAuth roles={["super_admin"]} />}>
                <Route path="/centers" element={<SuperAdminCenters />} />
              </Route>
              <Route
                element={<RequireAuth roles={["reception", "center_admin", "doctor"]} />}
              >
                <Route path="/schedule" element={<DoctorSchedule />} />
              </Route>
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
