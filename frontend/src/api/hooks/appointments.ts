import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAppointments,
  postAppointments,
  postAppointmentsByAppointmentIdReschedule,
  putAppointmentsByAppointmentIdStatus,
  type AppointmentCreate,
  type AppointmentReschedule,
  type AppointmentStatusUpdate
} from "../generated";

type AppointmentRange = {
  doctorId?: string | null;
  from?: string;
  to?: string;
};

export function useAppointments({ doctorId, from, to }: AppointmentRange) {
  return useQuery({
    queryKey: ["appointments", doctorId ?? null, from ?? null, to ?? null],
    queryFn: async () => {
      const response = await getAppointments({
        query: {
          doctor_id: doctorId ?? undefined,
          from,
          to
        },
        throwOnError: false
      });
      return response.data ?? [];
    }
  });
}

export function useCreateAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AppointmentCreate) => postAppointments({ body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["appointments"] });
      }
    }
  });
}

export function useRescheduleAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: string; body: AppointmentReschedule }) =>
      postAppointmentsByAppointmentIdReschedule({
        path: { appointmentId: input.id },
        body: input.body,
        throwOnError: false
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
    }
  });
}

export function useSetAppointmentStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: string; body: AppointmentStatusUpdate }) =>
      putAppointmentsByAppointmentIdStatus({
        path: { appointmentId: input.id },
        body: input.body,
        throwOnError: false
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appointments"] });
    }
  });
}
