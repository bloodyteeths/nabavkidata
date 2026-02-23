"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { mk } from "date-fns/locale";
import {
  Bell,
  Newspaper,
  Info,
  AlertTriangle,
  Check,
  CheckCheck,
  Trash2,
  Filter,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

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

export function NotificationList() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<"all" | "unread" | string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const router = useRouter();

  const pageSize = 20;

  useEffect(() => {
    fetchNotifications();
  }, [page, filter, typeFilter]);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const data = await api.getNotifications(
        page,
        pageSize,
        filter === "unread",
        typeFilter !== "all" ? typeFilter : undefined
      );
      setNotifications(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error("Error fetching notifications:", error);
      toast.error("Грешка при вчитување на известувања");
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
      toast.success("Сите известувања се означени како прочитани");
    } catch (error) {
      console.error("Error marking all as read:", error);
      toast.error("Грешка при означување");
    }
  };

  const handleMarkSelectedRead = async () => {
    if (selected.size === 0) return;

    try {
      await api.markNotificationRead(Array.from(selected));
      setNotifications((prev) =>
        prev.map((n) =>
          selected.has(n.notification_id) ? { ...n, is_read: true } : n
        )
      );
      setSelected(new Set());
      toast.success("Избраните известувања се означени како прочитани");
    } catch (error) {
      console.error("Error marking selected as read:", error);
      toast.error("Грешка при означување");
    }
  };

  const handleDeleteSelected = async () => {
    if (selected.size === 0) return;

    try {
      await Promise.all(
        Array.from(selected).map((id) => api.deleteNotification(id))
      );
      setNotifications((prev) =>
        prev.filter((n) => !selected.has(n.notification_id))
      );
      setSelected(new Set());
      toast.success("Избраните известувања се избришани");
    } catch (error) {
      console.error("Error deleting selected:", error);
      toast.error("Грешка при бришење");
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
      } catch (error) {
        console.error("Error marking notification as read:", error);
      }
    }

    // Navigate to relevant page
    if (notification.tender_id) {
      router.push(`/tenders/${encodeURIComponent(notification.tender_id)}`);
    } else if (notification.type === "briefing_ready") {
      router.push("/inbox");
    }
  };

  const toggleSelect = (id: string) => {
    const newSelected = new Set(selected);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelected(newSelected);
  };

  const toggleSelectAll = () => {
    if (selected.size === notifications.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(notifications.map((n) => n.notification_id)));
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
        return <Bell className="h-5 w-5 text-muted-foreground" />;
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

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      {/* Filters and Actions */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
        <div className="flex gap-2">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[150px]">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите</SelectItem>
              <SelectItem value="unread">Непрочитани</SelectItem>
            </SelectContent>
          </Select>

          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите типови</SelectItem>
              <SelectItem value="alert_match">Алерти</SelectItem>
              <SelectItem value="briefing_ready">Брифинзи</SelectItem>
              <SelectItem value="tender_update">Ажурирања</SelectItem>
              <SelectItem value="system">Системски</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex gap-2">
          {selected.size > 0 ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleMarkSelectedRead}
              >
                <Check className="h-4 w-4 mr-1" />
                Означи прочитано ({selected.size})
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDeleteSelected}
                className="text-red-400 hover:text-red-300"
              >
                <Trash2 className="h-4 w-4 mr-1" />
                Избриши ({selected.size})
              </Button>
            </>
          ) : (
            <Button variant="outline" size="sm" onClick={handleMarkAllRead}>
              <CheckCheck className="h-4 w-4 mr-1" />
              Означи сè прочитано
            </Button>
          )}
        </div>
      </div>

      {/* Bulk Select */}
      {notifications.length > 0 && (
        <div className="flex items-center gap-2 px-4 py-2 bg-foreground/5 rounded-lg">
          <input
            type="checkbox"
            checked={selected.size === notifications.length}
            onChange={toggleSelectAll}
            className="rounded border-gray-600"
          />
          <span className="text-sm text-muted-foreground">
            Избери сè ({notifications.length})
          </span>
        </div>
      )}

      {/* Notifications List */}
      {loading ? (
        <div className="p-8 text-center text-muted-foreground">
          Се вчитува...
        </div>
      ) : notifications.length === 0 ? (
        <div className="p-12 text-center">
          <Bell className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-lg font-medium mb-2">Немате известувања</p>
          <p className="text-sm text-muted-foreground">
            Кога ќе добиете известување, ќе се појави тука
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((notification) => (
            <div
              key={notification.notification_id}
              className={`flex gap-4 p-4 rounded-lg border transition-colors ${
                !notification.is_read
                  ? "bg-primary/5 border-primary/20"
                  : "bg-card/50 border-border"
              } hover:bg-foreground/5`}
            >
              <input
                type="checkbox"
                checked={selected.has(notification.notification_id)}
                onChange={() => toggleSelect(notification.notification_id)}
                className="mt-1 rounded border-gray-600"
              />

              <button
                onClick={() => handleNotificationClick(notification)}
                className="flex-1 flex gap-4 text-left"
              >
                <div className="flex-shrink-0 mt-1">
                  {getNotificationIcon(notification.type)}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p
                      className={`text-sm font-medium ${
                        !notification.is_read ? "text-foreground" : "text-muted-foreground"
                      }`}
                    >
                      {notification.title}
                    </p>
                    {!notification.is_read && (
                      <span className="flex-shrink-0 h-2 w-2 rounded-full bg-blue-500"></span>
                    )}
                  </div>
                  {notification.message && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {notification.message}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-2">
                    {getRelativeTime(notification.created_at)}
                  </p>
                </div>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 pt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Претходна
          </Button>
          <div className="flex items-center gap-2 px-4">
            <span className="text-sm text-muted-foreground">
              Страна {page} од {totalPages}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Следна
          </Button>
        </div>
      )}
    </div>
  );
}
