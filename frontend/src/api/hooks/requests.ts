import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getRequests,
  postRequests,
  postRequestsByRequestIdDecline,
  postRequestsByRequestIdFulfill,
  type AppointmentCreate,
  type AppointmentRequestCreate,
  type RequestDecline
} from "../generated";

type RequestStatus = "pending" | "fulfilled" | "declined";

export function useRequests(status?: RequestStatus) {
  return useQuery({
    queryKey: ["requests", status ?? null],
    queryFn: async () => {
      const response = await getRequests({
        query: status ? { status } : {},
        throwOnError: false
      });
      return response.data ?? [];
    }
  });
}

export function useCreateRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AppointmentRequestCreate) =>
      postRequests({ body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["requests"] });
      }
    }
  });
}

export function useFulfillRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: string; body: AppointmentCreate }) =>
      postRequestsByRequestIdFulfill({
        path: { requestId: input.id },
        body: input.body,
        throwOnError: false
      }),
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["requests"] });
        await queryClient.invalidateQueries({ queryKey: ["appointments"] });
      }
    }
  });
}

export function useDeclineRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: string; body: RequestDecline }) =>
      postRequestsByRequestIdDecline({
        path: { requestId: input.id },
        body: input.body,
        throwOnError: false
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["requests"] });
    }
  });
}
