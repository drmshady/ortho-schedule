import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getUsers,
  postUsers,
  putUsersByUserId,
  type UserCreate
} from "../generated";

type UserUpdate = {
  display_name?: string;
  is_active?: boolean;
  is_admin?: boolean;
};

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const response = await getUsers({ throwOnError: false });
      return response.data ?? [];
    }
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: UserCreate) => postUsers({ body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 201) {
        await queryClient.invalidateQueries({ queryKey: ["users"] });
      }
    }
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: string; body: UserUpdate }) =>
      putUsersByUserId({ path: { userId: input.id }, body: input.body, throwOnError: false }),
    onSuccess: async (result) => {
      if (result.response?.status === 200) {
        await queryClient.invalidateQueries({ queryKey: ["users"] });
      }
    }
  });
}
