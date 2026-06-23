import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getNotifications, postNotificationsByNotificationIdRead } from "../generated";

/** Poll cadence for the in-app notification bell (FR-026): in-app only, no push. */
const POLL_INTERVAL_MS = 45_000;

export function useNotifications(options?: { unreadOnly?: boolean }) {
  const unreadOnly = options?.unreadOnly ?? false;
  return useQuery({
    queryKey: ["notifications", unreadOnly],
    queryFn: async () => {
      const response = await getNotifications({
        query: unreadOnly ? { unread: true } : {},
        throwOnError: false
      });
      return response.data ?? [];
    },
    refetchInterval: POLL_INTERVAL_MS
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (notificationId: string) =>
      postNotificationsByNotificationIdRead({
        path: { notificationId },
        throwOnError: false
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  });
}
