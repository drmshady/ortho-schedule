import { useState } from "react";

import { useMarkNotificationRead, useNotifications } from "../api/hooks/notifications";
import type { Notification } from "../api/generated";

const TYPE_LABELS: Record<string, string> = {
  request_fulfilled: "Your appointment request was booked.",
  request_declined: "Your appointment request was declined.",
  request_created: "A new appointment request was submitted.",
  appt_reassign_needed: "An appointment needs reassignment."
};

function describe(notification: Notification): string {
  return TYPE_LABELS[notification.type ?? ""] ?? "Notification";
}

/** T069 — in-app notification bell with an unread badge and polling (FR-026, in-app only). */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const notifications = useNotifications();
  const markRead = useMarkNotificationRead();

  const items = notifications.data ?? [];
  const unreadCount = items.filter((item) => !item.is_read).length;

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
        className="relative rounded p-1 text-zinc-600 hover:bg-zinc-100"
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden className="text-lg">
          🔔
        </span>
        {unreadCount > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
            {unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-80 rounded-lg border border-zinc-200 bg-white p-2 text-sm shadow-lg">
          <p className="px-2 py-1 text-xs font-semibold uppercase text-zinc-400">Notifications</p>
          {items.length === 0 ? (
            <p className="px-2 py-3 text-center text-zinc-500">You're all caught up.</p>
          ) : (
            <ul className="max-h-80 divide-y divide-zinc-100 overflow-auto">
              {items.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    className={`flex w-full flex-col items-start gap-0.5 px-2 py-2 text-left hover:bg-zinc-50 ${
                      notification.is_read ? "text-zinc-500" : "font-medium text-zinc-900"
                    }`}
                    onClick={() => {
                      if (!notification.is_read && notification.id) {
                        markRead.mutate(notification.id);
                      }
                    }}
                  >
                    <span>{describe(notification)}</span>
                    {notification.created_at ? (
                      <span className="text-xs font-normal text-zinc-400">
                        {new Date(notification.created_at).toLocaleString()}
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
