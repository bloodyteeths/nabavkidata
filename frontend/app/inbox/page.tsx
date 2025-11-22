"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Mail, Inbox, Bell, CheckCircle, Circle } from "lucide-react"
import { formatDate } from "@/lib/utils"

interface EmailDigest {
  id: string
  title: string
  date: string
  type: "daily" | "weekly"
  read: boolean
  recommendedTenders: number
  competitorActivities: number
  preview: { tenders: string[]; competitors: string[] }
}

interface SystemAlert {
  id: string
  message: string
  date: string
  read: boolean
  severity: "info" | "warning" | "success"
}

const mockDigests: EmailDigest[] = [
  {
    id: "1", title: "Дневен преглед - 22 Ноември 2025", date: "2025-11-22", type: "daily", read: false,
    recommendedTenders: 5, competitorActivities: 3,
    preview: {
      tenders: ["Набавка на компјутерска опрема - УКИМ", "Услуги за одржување на софтвер - Општина Скопје", "Набавка на канцелариски материјали - МОН"],
      competitors: ["ТехКомпани победи на тендер за IT услуги", "СофтСолушнс учествува во 2 нови тендери", "ДигиталПро достави понуда за консалтинг"]
    }
  },
  {
    id: "2", title: "Дневен преглед - 21 Ноември 2025", date: "2025-11-21", type: "daily", read: true,
    recommendedTenders: 8, competitorActivities: 5,
    preview: {
      tenders: ["Развој на веб платформа - МИОА", "Набавка на мрежна опрема - Телеком", "Услуги за одржување - БЈС"],
      competitors: ["ТехКомпани достави понуда за мрежна опрема", "СофтСолушнс победи тендер за развој", "ДигиталПро учествува во 3 тендери"]
    }
  },
  {
    id: "3", title: "Неделен преглед - 15-21 Ноември 2025", date: "2025-11-21", type: "weekly", read: true,
    recommendedTenders: 42, competitorActivities: 18,
    preview: {
      tenders: ["Модернизација на IT инфраструктура - МВР", "Набавка на серверска опрема - АВРМ", "Развој на мобилна апликација - ФЗОМ"],
      competitors: ["ТехКомпани победи 4 тендери оваа недела", "СофтСолушнс активен во 12 тендери", "ДигиталПро нова понуда за консалтинг"]
    }
  },
  {
    id: "4", title: "Дневен преглед - 20 Ноември 2025", date: "2025-11-20", type: "daily", read: true,
    recommendedTenders: 6, competitorActivities: 4,
    preview: {
      tenders: ["Набавка на лиценци - МФ", "Услуги за обука - ДАРМ", "Набавка на принтери - МЗ"],
      competitors: ["ТехКомпани достави понуда за обука", "СофтСолушнс победи тендер за лиценци"]
    }
  },
  {
    id: "5", title: "Неделен преглед - 8-14 Ноември 2025", date: "2025-11-14", type: "weekly", read: false,
    recommendedTenders: 38, competitorActivities: 15,
    preview: {
      tenders: ["Дигитализација на процеси - МЖСПП", "Набавка на софтвер за управување - АППРМ", "Развој на ERP систем - ЕЛЕМ"],
      competitors: ["ТехКомпани победи 3 тендери", "СофтСолушнс учествува во 9 тендери", "ДигиталПро нови понуди за развој"]
    }
  }
]

const mockAlerts: SystemAlert[] = [
  { id: "1", message: "Нов тендер што одговара на вашите критериуми е објавен", date: "2025-11-22T10:30:00", read: false, severity: "info" },
  { id: "2", message: "Рокот за достава на понуда истекува за 2 дена", date: "2025-11-22T09:15:00", read: false, severity: "warning" },
  { id: "3", message: "Вашата омилена компанија достави нова понуда", date: "2025-11-21T16:45:00", read: true, severity: "info" },
  { id: "4", message: "Успешно се ажурираа податоците за тендери", date: "2025-11-21T08:00:00", read: true, severity: "success" },
  { id: "5", message: "3 нови тендери од вашата категорија", date: "2025-11-20T14:20:00", read: true, severity: "info" }
]

export default function InboxPage() {
  const [digests, setDigests] = useState<EmailDigest[]>(mockDigests)
  const [alerts, setAlerts] = useState<SystemAlert[]>(mockAlerts)
  const [filterType, setFilterType] = useState<"all" | "daily" | "weekly">("all")
  const [selectedDigest, setSelectedDigest] = useState<EmailDigest | null>(null)

  const filteredDigests = digests.filter((d) => filterType === "all" || d.type === filterType)
  const unreadDigestsCount = digests.filter((d) => !d.read).length
  const unreadAlertsCount = alerts.filter((a) => !a.read).length

  const toggleDigestRead = (id: string) => {
    setDigests(digests.map((d) => (d.id === id ? { ...d, read: !d.read } : d)))
    if (selectedDigest?.id === id) setSelectedDigest({ ...selectedDigest, read: !selectedDigest.read })
  }

  const toggleAlertRead = (id: string) => {
    setAlerts(alerts.map((a) => (a.id === id ? { ...a, read: !a.read } : a)))
  }

  const getSeverityColor = (severity: string) => {
    if (severity === "warning") return "bg-yellow-100 text-yellow-800 border-yellow-200"
    if (severity === "success") return "bg-green-100 text-green-800 border-green-200"
    return "bg-blue-100 text-blue-800 border-blue-200"
  }

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Приемно сандаче</h1>
        <p className="text-muted-foreground">Преглед на е-мејл дигести и системски известувања</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Вкупно дигести</CardTitle>
            <Inbox className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent><div className="text-2xl font-bold">{digests.length}</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Непрочитани дигести</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent><div className="text-2xl font-bold">{unreadDigestsCount}</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Непрочитани известувања</CardTitle>
            <Bell className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent><div className="text-2xl font-bold">{unreadAlertsCount}</div></CardContent>
        </Card>
      </div>

      <Tabs defaultValue="digests" className="space-y-4">
        <TabsList>
          <TabsTrigger value="digests"><Mail className="h-4 w-4 mr-2" />Е-мејл дигести</TabsTrigger>
          <TabsTrigger value="alerts"><Bell className="h-4 w-4 mr-2" />Системски известувања</TabsTrigger>
        </TabsList>

        <TabsContent value="digests" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                  <CardTitle>Дигести</CardTitle>
                  <CardDescription>Преглед на препорачани тендери и активности на конкуренти</CardDescription>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button variant={filterType === "all" ? "default" : "outline"} size="sm" onClick={() => setFilterType("all")}>Сите</Button>
                  <Button variant={filterType === "daily" ? "default" : "outline"} size="sm" onClick={() => setFilterType("daily")}>Дневни</Button>
                  <Button variant={filterType === "weekly" ? "default" : "outline"} size="sm" onClick={() => setFilterType("weekly")}>Неделни</Button>
                  <Button variant="ghost" size="sm" onClick={() => setDigests(digests.map((d) => ({ ...d, read: true })))}>Означи сè како прочитано</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="space-y-3">
                  {filteredDigests.map((digest) => (
                    <Card key={digest.id} className={`cursor-pointer transition-colors hover:bg-accent ${selectedDigest?.id === digest.id ? "border-primary" : ""} ${!digest.read ? "bg-blue-50" : ""}`} onClick={() => setSelectedDigest(digest)}>
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              {digest.read ? <CheckCircle className="h-4 w-4 text-green-600" /> : <Circle className="h-4 w-4 text-blue-600" />}
                              <h3 className={`font-semibold text-sm ${!digest.read ? "font-bold" : ""}`}>{digest.title}</h3>
                            </div>
                            <p className="text-xs text-muted-foreground mb-2">{formatDate(digest.date)}</p>
                            <div className="flex gap-2 flex-wrap">
                              <Badge variant="secondary" className="text-xs">{digest.type === "daily" ? "Дневен" : "Неделен"}</Badge>
                              <Badge variant="outline" className="text-xs">{digest.recommendedTenders} тендери</Badge>
                              <Badge variant="outline" className="text-xs">{digest.competitorActivities} активности</Badge>
                            </div>
                          </div>
                          <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); toggleDigestRead(digest.id) }}>
                            {digest.read ? "Непрочитано" : "Прочитано"}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <div>
                  {selectedDigest ? (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-lg">{selectedDigest.title}</CardTitle>
                        <CardDescription>{formatDate(selectedDigest.date)}</CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div>
                          <h4 className="font-semibold mb-2 flex items-center gap-2">
                            <Inbox className="h-4 w-4" />Препорачани тендери ({selectedDigest.recommendedTenders})
                          </h4>
                          <ul className="space-y-2">
                            {selectedDigest.preview.tenders.map((tender, idx) => (
                              <li key={idx} className="text-sm pl-6 relative"><span className="absolute left-0 top-1">•</span>{tender}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <h4 className="font-semibold mb-2 flex items-center gap-2">
                            <Bell className="h-4 w-4" />Активности на конкуренти ({selectedDigest.competitorActivities})
                          </h4>
                          <ul className="space-y-2">
                            {selectedDigest.preview.competitors.map((activity, idx) => (
                              <li key={idx} className="text-sm pl-6 relative"><span className="absolute left-0 top-1">•</span>{activity}</li>
                            ))}
                          </ul>
                        </div>
                      </CardContent>
                    </Card>
                  ) : (
                    <Card className="h-full flex items-center justify-center">
                      <CardContent className="text-center text-muted-foreground p-8">
                        <Mail className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>Изберете дигест за преглед на детали</p>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Системски известувања</CardTitle>
                  <CardDescription>Важни пораки и ажурирања од системот</CardDescription>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setAlerts(alerts.map((a) => ({ ...a, read: true })))}>Означи сè како прочитано</Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <Card key={alert.id} className={`${!alert.read ? "border-l-4 border-l-primary bg-blue-50" : ""}`}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <Badge className={getSeverityColor(alert.severity)}>
                              {alert.severity === "warning" && "Предупредување"}
                              {alert.severity === "success" && "Успех"}
                              {alert.severity === "info" && "Информација"}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {new Date(alert.date).toLocaleString("mk-MK", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                            </span>
                          </div>
                          <p className={`text-sm ${!alert.read ? "font-semibold" : ""}`}>{alert.message}</p>
                        </div>
                        <Button variant="ghost" size="sm" onClick={() => toggleAlertRead(alert.id)}>
                          {alert.read ? <Circle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4 text-green-600" />}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
