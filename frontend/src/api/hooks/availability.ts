import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteAvailabilityExceptionsByExceptionId,
  deleteAvailabilityTemplatesByTemplateId,
  getAvailabilityExceptions,
  getAvailabilitySlots,
  getAvailabilityTemplates,
  getDoctors,
  postAvailabilityExceptions,
  postAvailabilityTemplates,
  type AvailabilityException,
  type AvailabilityTemplate
} from "../generated";

export function useDoctors() {
  return useQuery({
    queryKey: ["doctors"],
    queryFn: async () => {
      const response = await getDoctors({ throwOnError: false });
      return response.data ?? [];
    }
  });
}

export function useSlots(doctorId: string | null, date: string | null) {
  return useQuery({
    queryKey: ["slots", doctorId, date],
    enabled: Boolean(doctorId && date),
    queryFn: async () => {
      const response = await getAvailabilitySlots({
        query: { doctor_id: doctorId ?? undefined, date: date ?? undefined },
        throwOnError: false
      });
      return response.data ?? [];
    }
  });
}

export function useTemplates(doctorId: string | null) {
  return useQuery({
    queryKey: ["templates", doctorId],
    enabled: Boolean(doctorId),
    queryFn: async () => {
      const response = await getAvailabilityTemplates({
        query: { doctor_id: doctorId ?? undefined },
        throwOnError: false
      });
      return response.data ?? [];
    }
  });
}

export function useCreateTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AvailabilityTemplate) =>
      postAvailabilityTemplates({ body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["templates"] });
        await queryClient.invalidateQueries({ queryKey: ["slots"] });
      }
    }
  });
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      deleteAvailabilityTemplatesByTemplateId({ path: { templateId: id }, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 204) {
        await queryClient.invalidateQueries({ queryKey: ["templates"] });
        await queryClient.invalidateQueries({ queryKey: ["slots"] });
      }
    }
  });
}

export function useExceptions(doctorId: string | null) {
  return useQuery({
    queryKey: ["exceptions", doctorId],
    enabled: Boolean(doctorId),
    queryFn: async () => {
      const response = await getAvailabilityExceptions({
        query: { doctor_id: doctorId ?? undefined },
        throwOnError: false
      });
      return response.data ?? [];
    }
  });
}

export function useCreateException() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AvailabilityException) =>
      postAvailabilityExceptions({ body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["exceptions"] });
        await queryClient.invalidateQueries({ queryKey: ["slots"] });
      }
    }
  });
}

export function useDeleteException() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      deleteAvailabilityExceptionsByExceptionId({
        path: { exceptionId: id },
        throwOnError: false
      }),
    onSuccess: async (result) => {
      if (result.response?.status === 204) {
        await queryClient.invalidateQueries({ queryKey: ["exceptions"] });
        await queryClient.invalidateQueries({ queryKey: ["slots"] });
      }
    }
  });
}
