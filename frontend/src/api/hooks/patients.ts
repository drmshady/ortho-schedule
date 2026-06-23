import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getPatients, postPatients, type PatientCreate } from "../generated";

export function usePatientSearch(q: string) {
  return useQuery({
    queryKey: ["patients", q],
    queryFn: async () => {
      const response = await getPatients({ query: q ? { q } : {}, throwOnError: false });
      return response.data ?? [];
    }
  });
}

/**
 * Registers a patient. Resolves with the raw response so callers can branch on the
 * non-blocking `409 possible_duplicate` warning before confirming.
 */
export function useCreatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: PatientCreate) => {
      return postPatients({ body, throwOnError: false });
    },
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["patients"] });
      }
    }
  });
}
