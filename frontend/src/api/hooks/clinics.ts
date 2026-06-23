import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteClinicsByClinicId,
  getClinics,
  postClinics,
  putClinicsByClinicId,
  type ClinicCreate,
  type ClinicUpdate
} from "../generated";

export function useClinics() {
  return useQuery({
    queryKey: ["clinics"],
    queryFn: async () => {
      const response = await getClinics({ throwOnError: false });
      return response.data ?? [];
    }
  });
}

export function useCreateClinic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ClinicCreate) => postClinics({ body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["clinics"] });
      }
    }
  });
}

export function useUpdateClinic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: string; body: ClinicUpdate }) =>
      putClinicsByClinicId({ path: { clinicId: input.id }, body: input.body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 200) {
        await queryClient.invalidateQueries({ queryKey: ["clinics"] });
      }
    }
  });
}

export function useDeleteClinic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      deleteClinicsByClinicId({ path: { clinicId: id }, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 204) {
        await queryClient.invalidateQueries({ queryKey: ["clinics"] });
      }
    }
  });
}
