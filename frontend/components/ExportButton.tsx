"use client";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

interface ExportButtonProps {
  data: any[];
  filename: string;
  columns: { key: string; label: string }[];
}

export function ExportButton({ data, filename, columns }: ExportButtonProps) {
  const exportToCSV = () => {
    const headers = columns.map(c => c.label).join(",");
    const rows = data.map(item =>
      columns.map(c => {
        const val = item[c.key];
        // Escape quotes and wrap in quotes if contains comma
        if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
          return `"${val.replace(/"/g, '""')}"`;
        }
        return val ?? '';
      }).join(",")
    );
    const csv = [headers, ...rows].join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${filename}.csv`;
    link.click();
  };

  return (
    <Button variant="outline" size="sm" onClick={exportToCSV}>
      <Download className="h-4 w-4 mr-2" />
      Извези CSV
    </Button>
  );
}
