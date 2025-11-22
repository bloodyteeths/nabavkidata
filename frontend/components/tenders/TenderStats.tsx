import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, CheckCircle, XCircle, Clock } from "lucide-react";

interface TenderStatsProps {
  total: number;
  open: number;
  closed: number;
  awarded: number;
}

export function TenderStats({ total, open, closed, awarded }: TenderStatsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            Вкупно
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{total}</div>
          <p className="text-xs text-muted-foreground">Тендери</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Clock className="h-4 w-4 text-green-600" />
            Отворени
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{open}</div>
          <p className="text-xs text-muted-foreground">Активни</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <XCircle className="h-4 w-4 text-orange-600" />
            Затворени
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{closed}</div>
          <p className="text-xs text-muted-foreground">Завршени</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-blue-600" />
            Доделени
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{awarded}</div>
          <p className="text-xs text-muted-foreground">Добиени</p>
        </CardContent>
      </Card>
    </div>
  );
}
