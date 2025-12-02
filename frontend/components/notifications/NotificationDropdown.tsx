"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { mk } from "date-fns/locale";
import { Bell, Newspaper, Info, AlertTriangle, Check, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import Link from "next/link";

interface Notification {
  notification_id: string;
  type: string;
  title: string;
  message?: string;
  data: Record<string, any>;
  is_read: boolean;
  created_at: string;
  tender_id?: string;
  alert_id?: string;
}

interface NotificationDropdownProps {
  onNotificationRead: () => void;
  onClose: () => void;
}

export function NotificationDropdown({
  onNotificationRead,
  onClose,
}: NotificationDropdownProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const data = await api.getNotifications(1, 10, false);
      setNotifications(data.items || []);
    } catch (error) {
      console.error("Error fetching notifications:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllRead();
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true }))
      );
      onNotificationRead();
    } catch (error) {
      console.error("Error marking all as read:", error);
    }
  };

  const handleNotificationClick = async (notification: Notification) => {
    // Mark as read
    if (!notification.is_read) {
      try {
        await api.markNotificationRead(notification.notification_id);
        setNotifications((prev) =>
          prev.map((n) =>
            n.notification_id === notification.notification_id
              ? { ...n, is_read: true }
              : n
          )
        );
        onNotificationRead();
      } catch (error) {
        console.error("Error marking notification as read:", error);
      }
    }

    // Navigate to relevant page
    if (notification.tender_id) {
      router.push(`/tenders/${encodeURIComponent(notification.tender_id)}`);
      onClose();
    } else if (notification.type === "briefing_ready") {
      router.push("/inbox");
      onClose();
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case "alert_match":
        return <Bell className="h-5 w-5 text-blue-400" />;
      case "briefing_ready":
        return <Newspaper className="h-5 w-5 text-green-400" />;
      case "tender_update":
        return <AlertTriangle className="h-5 w-5 text-yellow-400" />;
      case "system":
        return <Info className="h-5 w-5 text-purple-400" />;
      default:
        return <Bell className="h-5 w-5 text-gray-400" />;
    }
  };

  const getRelativeTime = (dateString: string) => {
    try {
      return formatDistanceToNow(new Date(dateString), {
        addSuffix: true,
        locale: mk,
      });
    } catch (error) {
      return dateString;
    }
  };

  return (
    <div className="flex flex-col max-h-[500px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <h3 className="font-semibold text-white">Известувања</h3>
        {notifications.some((n) => !n.is_read) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleMarkAllRead}
            className="text-xs hover:bg-white/5"
          >
            <Check className="h-3 w-3 mr-1" />
            Означи сè како прочитано
          </Button>
        )}
      </div>

      {/* Notifications List */}
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">
            Се вчитува...
          </div>
        ) : notifications.length === 0 ? (
          <div className="p-8 text-center">
            <Bell className="h-12 w-12 mx-auto mb-2 text-muted-foreground opacity-50" />
            <p className="text-sm text-muted-foreground">
              Немате нови известувања
            </p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {notifications.map((notification) => (
              <button
                key={notification.notification_id}
                onClick={() => handleNotificationClick(notification)}
                className={`w-full p-4 text-left transition-colors hover:bg-white/5 ${
                  !notification.is_read ? "bg-primary/5" : ""
                }`}
              >
                <div className="flex gap-3">
                  <div className="flex-shrink-0 mt-1">
                    {getNotificationIcon(notification.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p
                        className={`text-sm font-medium ${
                          !notification.is_read
                            ? "text-white"
                            : "text-gray-300"
                        }`}
                      >
                        {notification.title}
                      </p>
                      {!notification.is_read && (
                        <span className="flex-shrink-0 h-2 w-2 rounded-full bg-blue-500"></span>
                      )}
                    </div>
                    {notification.message && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {notification.message}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">
                      {getRelativeTime(notification.created_at)}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Footer */}
      {notifications.length > 0 && (
        <div className="p-3 border-t border-white/10 bg-black/20">
          <Link
            href="/notifications"
            onClick={onClose}
            className="flex items-center justify-center gap-2 text-sm text-primary hover:text-primary/80 transition-colors"
          >
            Прегледај ги сите известувања
            <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
      )}
    </div>
  );
}
