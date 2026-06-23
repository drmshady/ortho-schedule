import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getCenters,
  postCenters,
  putCentersByCenterId,
  putCentersByCenterIdStatus,
  type CenterCreate
} from "../generated";

export function useCenters() {
  return useQuery({
    queryKey: ["centers"],
    queryFn: async () => {
      const response = await getCenters({ throwOnError: false });
      return response.data ?? [];
    }
  });
}

export function useCreateCenter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: CenterCreate) => postCenters({ body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["centers"] });
      }
    }
  });
}

export function useUpdateCenterTimezone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: string; timezone: string }) =>
      putCentersByCenterId({
        path: { centerId: input.id },
        body: { timezone: input.timezone },
        throwOnError: false
      }),
    onSuccess: async (result) => {
      if (result.response?.status === 200) {
        await queryClient.invalidateQueries({ queryKey: ["centers"] });
      }
    }
  });
}

export function useSetCenterStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: string; status: "active" | "suspended" }) =>
      putCentersByCenterIdStatus({
        path: { centerId: input.id },
        body: { status: input.status },
        throwOnError: false
      }),
    onSuccess: async (result) => {
      if (result.response?.status === 200) {
        await queryClient.invalidateQueries({ queryKey: ["centers"] });
      }
    }
  });
}
