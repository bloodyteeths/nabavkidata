import { Metadata } from "next";
import { NotificationList } from "@/components/notifications/NotificationList";

export const metadata: Metadata = {
  title: "Известувања",
  description: "Прегледај ги твоите известувања и алерти",
};

export default function NotificationsPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Известувања</h1>
        <p className="text-muted-foreground">
          Прегледај ги твоите известувања, алерти и ажурирања
        </p>
      </div>

      <NotificationList />
    </div>
  );
}
