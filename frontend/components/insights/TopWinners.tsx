"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Trophy, TrendingUp, Building, Search, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface Winner {
  name: string;
  win_count: number;
  total_value_won: number;
  categories: string[];
  avg_contract_value: number;
}

interface TopWinnersData {
  winners: Winner[];
  total_awarded: number;
}

export function TopWinners() {
  const [data, setData] = useState<TopWinnersData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cpvFilter, setCpvFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    loadData();
  }, [searchTerm]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getTopWinners(searchTerm || undefined);
      setData(result);
    } catch (err: any) {
      console.error("Failed to load top winners:", err);
      setError(err.message || "Failed to load top winners");
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number): string => {
    if (value >= 1_000_000_000) {
      return `${(value / 1_000_000_000).toFixed(2)} млрд`;
    } else if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(2)} мил`;
    } else if (value >= 1_000) {
      return `${(value / 1_000).toFixed(0)} илј`;
    }
    return value.toLocaleString();
  };

  const getRankBadgeVariant = (rank: number) => {
    if (rank === 1) return "default";
    if (rank === 2) return "secondary";
    if (rank === 3) return "secondary";
    return "outline";
  };

  const getRankIcon = (rank: number) => {
    if (rank <= 3) {
      return (
        <Trophy
          className={`h-5 w-5 ${
            rank === 1
              ? "text-yellow-500 fill-yellow-500"
              : rank === 2
              ? "text-gray-400 fill-gray-400"
              : "text-orange-600 fill-orange-600"
          }`}
        />
      );
    }
    return <span className="text-sm font-semibold text-muted-foreground">#{rank}</span>;
  };

  const handleSearch = () => {
    setCpvFilter(searchTerm);
    loadData();
  };

  const maxWinCount = data?.winners[0]?.win_count || 1;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Trophy className="h-6 w-6 text-yellow-500" />
              Топ Победници
            </CardTitle>
            <CardDescription>
              Компании со најмногу добиени тендери - вашата конкуренција
            </CardDescription>
          </div>
          {data && (
            <div className="text-right">
              <p className="text-sm text-muted-foreground">Вкупно доделени</p>
              <p className="text-2xl font-bold">{data.total_awarded.toLocaleString()}</p>
            </div>
          )}
        </div>

        {/* CPV Code Filter */}
        <div className="flex gap-2 mt-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Филтрирај по CPV код (пр: 45000000)"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSearch();
                }
              }}
              className="pl-9"
            />
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-destructive">{error}</p>
          </div>
        ) : !data || data.winners.length === 0 ? (
          <div className="text-center py-12">
            <Trophy className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Нема податоци за приказ</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-20">Ранг</TableHead>
                  <TableHead>Компанија</TableHead>
                  <TableHead className="text-center">Победи</TableHead>
                  <TableHead className="text-right">Вкупна вредност</TableHead>
                  <TableHead className="text-right">Просечен договор</TableHead>
                  <TableHead>Категории</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.winners.map((winner, index) => {
                  const rank = index + 1;
                  const winPercentage = (winner.win_count / maxWinCount) * 100;

                  return (
                    <TableRow
                      key={winner.name}
                      className={
                        rank <= 3
                          ? rank === 1
                            ? "bg-yellow-50/50 dark:bg-yellow-950/10"
                            : rank === 2
                            ? "bg-gray-50/50 dark:bg-gray-950/10"
                            : "bg-orange-50/50 dark:bg-orange-950/10"
                          : ""
                      }
                    >
                      <TableCell>
                        <div className="flex items-center justify-center">
                          {getRankIcon(rank)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Building className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          <span className="font-medium">{winner.name}</span>
                          {rank <= 3 && (
                            <Badge variant={getRankBadgeVariant(rank)} className="ml-auto">
                              {rank === 1 ? "Прво место" : rank === 2 ? "Второ место" : "Трето место"}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center justify-center gap-2">
                            <TrendingUp className="h-4 w-4 text-green-600" />
                            <span className="font-bold text-green-600">
                              {winner.win_count.toLocaleString()}
                            </span>
                          </div>
                          {/* Progress bar showing relative win count */}
                          <div className="w-full bg-muted rounded-full h-1.5">
                            <div
                              className="bg-gradient-to-r from-green-500 to-emerald-600 h-1.5 rounded-full transition-all"
                              style={{ width: `${winPercentage}%` }}
                            />
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className="font-semibold">
                          {formatCurrency(winner.total_value_won)} МКД
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className="text-muted-foreground">
                          {formatCurrency(winner.avg_contract_value)} МКД
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {winner.categories.slice(0, 3).map((category) => (
                            <Badge
                              key={category}
                              variant="outline"
                              className="text-xs whitespace-nowrap"
                            >
                              {category}
                            </Badge>
                          ))}
                          {winner.categories.length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{winner.categories.length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
