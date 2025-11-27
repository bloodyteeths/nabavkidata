"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Mail, Inbox, Bell, CheckCircle, Circle, AlertCircle } from "lucide-react"
import { formatDate, formatDateTime } from "@/lib/utils"
import { useAuth } from "@/lib/auth"
import { api } from "@/lib/api"

interface EmailDigest {
  id: string
  date: string
  tender_count: number
  competitor_activity_count: number
  sent: boolean
  sent_at: string | null
  preview: {
    text: string
  }
}

interface EmailDigestDetail extends EmailDigest {
  html: string
  text: string
}

interface SystemAlert {
  id: string
  message: string
  date: string
  read: boolean
  severity: "info" | "warning" | "success"
}

// Mock alerts for now - will need backend endpoint
const mockAlerts: SystemAlert[] = [
  { id: "1", message: "Нов тендер што одговара на вашите критериуми е објавен", date: "2025-11-22T10:30:00", read: false, severity: "info" },
  { id: "2", message: "Рокот за достава на понуда истекува за 2 дена", date: "2025-11-22T09:15:00", read: false, severity: "warning" },
  { id: "3", message: "Вашата омилена компанија достави нова понуда", date: "2025-11-21T16:45:00", read: true, severity: "info" },
  { id: "4", message: "Успешно се ажурираа податоците за тендери", date: "2025-11-21T08:00:00", read: true, severity: "success" },
  { id: "5", message: "3 нови тендери од вашата категорија", date: "2025-11-20T14:20:00", read: true, severity: "info" }
]

export default function InboxPage() {
  const { user } = useAuth()
  const [digests, setDigests] = useState<EmailDigest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [alerts, setAlerts] = useState<SystemAlert[]>(mockAlerts)
  const [selectedDigest, setSelectedDigest] = useState<EmailDigestDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  useEffect(() => {
    if (user) {
      loadDigests()
    }
  }, [user])

  async function loadDigests() {
    if (!user) return

    try {
      setLoading(true)
      setError(null)
      const response = await api.getDigests(user.user_id, 50, 0)
      setDigests(response.items)
    } catch (err) {
      console.error("Failed to load digests:", err)
      setError("Не можевме да ги вчитаме дигестите. Ве молиме обидете се повторно.")
    } finally {
      setLoading(false)
    }
  }

  async function loadDigestDetail(digestId: string) {
    if (!user) return

    try {
      setLoadingDetail(true)
      const detail = await api.getDigestDetail(digestId, user.user_id)
      setSelectedDigest(detail as EmailDigestDetail)
    } catch (err) {
      console.error("Failed to load digest detail:", err)
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleDigestClick = async (digest: EmailDigest) => {
    await loadDigestDetail(digest.id)
  }

  const unreadDigestsCount = digests.filter((d) => !d.sent).length
  const unreadAlertsCount = alerts.filter((a) => !a.read).length

  const toggleAlertRead = (id: string) => {
    setAlerts(alerts.map((a) => (a.id === id ? { ...a, read: !a.read } : a)))
  }

  const getSeverityColor = (severity: string) => {
    if (severity === "warning") return "bg-yellow-100 text-yellow-800 border-yellow-200"
    if (severity === "success") return "bg-green-100 text-green-800 border-green-200"
    return "bg-blue-100 text-blue-800 border-blue-200"
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <Card className="max-w-md">
          <CardContent className="p-6 text-center">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <h3 className="text-lg font-semibold mb-2">Грешка при вчитување</h3>
            <p className="text-muted-foreground mb-4">{error}</p>
            <Button onClick={loadDigests}>Обиди се повторно</Button>
          </CardContent>
        </Card>
      </div>
    )
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
                  <Button variant="ghost" size="sm" onClick={loadDigests}>Освежи</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {digests.length === 0 ? (
                <div className="text-center py-12">
                  <Mail className="h-12 w-12 mx-auto mb-4 opacity-50 text-muted-foreground" />
                  <h3 className="text-lg font-semibold mb-2">Нема дигести</h3>
                  <p className="text-muted-foreground">Дигестите ќе се појават овде кога системот ги генерира.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="space-y-3">
                    {digests.map((digest) => (
                      <Card
                        key={digest.id}
                        className={`cursor-pointer transition-colors hover:bg-accent ${selectedDigest?.id === digest.id ? "border-primary" : ""} ${!digest.sent ? "bg-blue-50" : ""}`}
                        onClick={() => handleDigestClick(digest)}
                      >
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                {digest.sent ? <CheckCircle className="h-4 w-4 text-green-600" /> : <Circle className="h-4 w-4 text-blue-600" />}
                                <h3 className={`font-semibold text-sm ${!digest.sent ? "font-bold" : ""}`}>
                                  Дигест - {formatDate(digest.date, { year: "numeric", month: "long", day: "numeric" })}
                                </h3>
                              </div>
                              <p className="text-xs text-muted-foreground mb-2">{formatDate(digest.date)}</p>
                              <div className="flex gap-2 flex-wrap">
                                <Badge variant="outline" className="text-xs">{digest.tender_count} тендери</Badge>
                                <Badge variant="outline" className="text-xs">{digest.competitor_activity_count} активности</Badge>
                                {digest.sent && <Badge variant="secondary" className="text-xs">Испратено</Badge>}
                              </div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                </div>

                  <div>
                    {loadingDetail ? (
                      <Card className="h-full flex items-center justify-center">
                        <CardContent className="text-center p-8">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                          <p className="text-muted-foreground mt-4">Вчитување...</p>
                        </CardContent>
                      </Card>
                    ) : selectedDigest ? (
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">
                            Дигест - {formatDate(selectedDigest.date, { year: "numeric", month: "long", day: "numeric" })}
                          </CardTitle>
                          <CardDescription>{formatDate(selectedDigest.date)}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          <div>
                            <h4 className="font-semibold mb-2 flex items-center gap-2">
                              <Inbox className="h-4 w-4" />Препорачани тендери ({selectedDigest.tender_count})
                            </h4>
                            {selectedDigest.text && (
                              <p className="text-sm text-muted-foreground mb-3">{selectedDigest.text}</p>
                            )}
                          </div>
                          <div>
                            <h4 className="font-semibold mb-2 flex items-center gap-2">
                              <Bell className="h-4 w-4" />Активности на конкуренти ({selectedDigest.competitor_activity_count})
                            </h4>
                          </div>
                          {selectedDigest.html && (
                            <div className="mt-4 border-t pt-4">
                              <div
                                className="prose prose-sm max-w-none"
                                dangerouslySetInnerHTML={{ __html: selectedDigest.html }}
                              />
                            </div>
                          )}
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
              )}
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
                              {formatDateTime(alert.date, {
                                day: "numeric",
                                month: "short",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
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
