"use client"

import { useState, useEffect, useCallback } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Mail, Inbox, Bell, CheckCircle, Circle, AlertCircle, Loader2 } from "lucide-react"
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

interface Notification {
  notification_id: string
  user_id: string
  type: string
  title: string
  message?: string
  data: Record<string, any>
  tender_id?: string
  alert_id?: string
  is_read: boolean
  created_at: string
}

const PAGE_SIZE = 10

export default function InboxPage() {
  const { user } = useAuth()
  const [digests, setDigests] = useState<EmailDigest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [notificationsLoading, setNotificationsLoading] = useState(true)
  const [notificationsError, setNotificationsError] = useState<string | null>(null)
  const [notificationsTotal, setNotificationsTotal] = useState(0)
  const [notificationsPage, setNotificationsPage] = useState(1)
  const [loadingMore, setLoadingMore] = useState(false)
  const [markingRead, setMarkingRead] = useState<string | null>(null)
  const [markingAllRead, setMarkingAllRead] = useState(false)
  const [selectedDigest, setSelectedDigest] = useState<EmailDigestDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const loadNotifications = useCallback(async (page: number = 1, append: boolean = false) => {
    try {
      if (append) {
        setLoadingMore(true)
      } else {
        setNotificationsLoading(true)
      }
      setNotificationsError(null)
      const response = await api.getNotifications(page, PAGE_SIZE)
      if (append) {
        setNotifications(prev => [...prev, ...response.items])
      } else {
        setNotifications(response.items)
      }
      setNotificationsTotal(response.total)
      setNotificationsPage(page)
    } catch (err) {
      console.error("Failed to load notifications:", err)
      setNotificationsError("Не можевме да ги вчитаме известувањата. Ве молиме обидете се повторно.")
    } finally {
      setNotificationsLoading(false)
      setLoadingMore(false)
    }
  }, [])

  useEffect(() => {
    if (user) {
      loadDigests()
      loadNotifications(1)
    }
  }, [user, loadNotifications])

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
  const unreadAlertsCount = notifications.filter((n) => !n.is_read).length
  const hasMoreNotifications = notifications.length < notificationsTotal

  async function handleMarkRead(notificationId: string) {
    setMarkingRead(notificationId)
    try {
      await api.markNotificationRead(notificationId)
      setNotifications(prev =>
        prev.map(n => n.notification_id === notificationId ? { ...n, is_read: !n.is_read } : n)
      )
    } catch (err) {
      console.error("Failed to mark notification:", err)
    } finally {
      setMarkingRead(null)
    }
  }

  async function handleMarkAllRead() {
    setMarkingAllRead(true)
    try {
      await api.markAllRead()
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
    } catch (err) {
      console.error("Failed to mark all as read:", err)
    } finally {
      setMarkingAllRead(false)
    }
  }

  function handleLoadMore() {
    loadNotifications(notificationsPage + 1, true)
  }

  const getTypeColor = (type: string) => {
    if (type === "alert_match" || type === "warning") return "bg-yellow-100 text-yellow-800 border-yellow-200"
    if (type === "success" || type === "welcome") return "bg-green-100 text-green-800 border-green-200"
    return "bg-blue-100 text-blue-800 border-blue-200"
  }

  const getTypeLabel = (type: string) => {
    if (type === "alert_match") return "Совпаѓање"
    if (type === "warning") return "Предупредување"
    if (type === "success" || type === "welcome") return "Успех"
    if (type === "deadline") return "Рок"
    if (type === "system") return "Систем"
    return "Информација"
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
    <div className="container mx-auto p-3 md:p-6 max-w-7xl">
      <div className="mb-4 md:mb-6">
        <h1 className="text-2xl md:text-3xl font-bold mb-1 md:mb-2">Приемно сандаче</h1>
        <p className="text-xs md:text-sm text-muted-foreground">Преглед на е-мејл дигести и системски известувања</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 md:gap-4 mb-4 md:mb-6">
        <Card className="col-span-2 md:col-span-1">
          <CardHeader className="flex flex-row items-center justify-between pb-2 p-4 md:p-6">
            <CardTitle className="text-xs md:text-sm font-medium">Вкупно дигести</CardTitle>
            <Inbox className="h-3 w-3 md:h-4 md:w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0"><div className="text-xl md:text-2xl font-bold">{digests.length}</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 p-4 md:p-6">
            <CardTitle className="text-xs md:text-sm font-medium">Непрочитани дигести</CardTitle>
            <Mail className="h-3 w-3 md:h-4 md:w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0"><div className="text-xl md:text-2xl font-bold">{unreadDigestsCount}</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 p-4 md:p-6">
            <CardTitle className="text-xs md:text-sm font-medium">Непрочитани известувања</CardTitle>
            <Bell className="h-3 w-3 md:h-4 md:w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="p-4 md:p-6 pt-0"><div className="text-xl md:text-2xl font-bold">{unreadAlertsCount}</div></CardContent>
        </Card>
      </div>

      <Tabs defaultValue="digests" className="space-y-3 md:space-y-4">
        <TabsList className="h-9 md:h-10">
          <TabsTrigger value="digests" className="text-xs md:text-sm"><Mail className="h-3 w-3 md:h-4 md:w-4 mr-2" />Е-мејл дигести</TabsTrigger>
          <TabsTrigger value="alerts" className="text-xs md:text-sm"><Bell className="h-3 w-3 md:h-4 md:w-4 mr-2" />Системски известувања</TabsTrigger>
        </TabsList>

        <TabsContent value="digests" className="space-y-3 md:space-y-4">
          <Card>
            <CardHeader className="p-4 md:p-6">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-4">
                <div>
                  <CardTitle className="text-lg md:text-xl">Дигести</CardTitle>
                  <CardDescription className="text-xs md:text-sm">Преглед на препорачани тендери и активности на конкуренти</CardDescription>
                </div>
                <div className="flex gap-2 flex-wrap w-full sm:w-auto">
                  <Button variant="ghost" size="sm" onClick={loadDigests} className="w-full sm:w-auto h-8 md:h-9 text-xs md:text-sm">Освежи</Button>
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
                        <CardContent className="p-3 md:p-4">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                {digest.sent ? <CheckCircle className="h-3 w-3 md:h-4 md:w-4 text-green-600" /> : <Circle className="h-3 w-3 md:h-4 md:w-4 text-blue-600" />}
                                <h3 className={`font-semibold text-xs md:text-sm ${!digest.sent ? "font-bold" : ""}`}>
                                  Дигест - {formatDate(digest.date, { year: "numeric", month: "long", day: "numeric" })}
                                </h3>
                              </div>
                              <p className="text-[10px] md:text-xs text-muted-foreground mb-2">{formatDate(digest.date)}</p>
                              <div className="flex gap-2 flex-wrap">
                                <Badge variant="outline" className="text-[10px] md:text-xs px-1.5 py-0">{digest.tender_count} тендери</Badge>
                                <Badge variant="outline" className="text-[10px] md:text-xs px-1.5 py-0">{digest.competitor_activity_count} активности</Badge>
                                {digest.sent && <Badge variant="secondary" className="text-[10px] md:text-xs px-1.5 py-0">Испратено</Badge>}
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

        <TabsContent value="alerts" className="space-y-3 md:space-y-4">
          <Card>
            <CardHeader className="p-4 md:p-6">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-0">
                <div>
                  <CardTitle className="text-lg md:text-xl">Системски известувања</CardTitle>
                  <CardDescription className="text-xs md:text-sm">Важни пораки и ажурирања од системот</CardDescription>
                </div>
                <div className="flex gap-2 w-full sm:w-auto">
                  <Button variant="ghost" size="sm" onClick={() => loadNotifications(1)} className="w-full sm:w-auto h-8 md:h-9 text-xs md:text-sm">Освежи</Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleMarkAllRead}
                    disabled={markingAllRead || unreadAlertsCount === 0}
                    className="w-full sm:w-auto h-8 md:h-9 text-xs md:text-sm"
                  >
                    {markingAllRead ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                    Означи сè како прочитано
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {notificationsLoading ? (
                <div className="space-y-3">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="animate-pulse">
                      <div className="h-20 bg-muted rounded-lg" />
                    </div>
                  ))}
                </div>
              ) : notificationsError ? (
                <div className="text-center py-12">
                  <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive opacity-50" />
                  <h3 className="text-lg font-semibold mb-2">Грешка при вчитување</h3>
                  <p className="text-muted-foreground mb-4 text-sm">{notificationsError}</p>
                  <Button variant="outline" size="sm" onClick={() => loadNotifications(1)}>Обиди се повторно</Button>
                </div>
              ) : notifications.length === 0 ? (
                <div className="text-center py-12">
                  <Bell className="h-12 w-12 mx-auto mb-4 opacity-50 text-muted-foreground" />
                  <h3 className="text-lg font-semibold mb-2">Нема известувања</h3>
                  <p className="text-muted-foreground text-sm">Кога ќе има нови совпаѓања или системски пораки, ќе се појават овде.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {notifications.map((notif) => (
                    <Card key={notif.notification_id} className={`${!notif.is_read ? "border-l-4 border-l-primary bg-blue-50" : ""}`}>
                      <CardContent className="p-3 md:p-4">
                        <div className="flex items-start justify-between gap-3 md:gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1 md:mb-2 flex-wrap">
                              <Badge className={`${getTypeColor(notif.type)} text-[10px] md:text-xs px-1.5 py-0`}>
                                {getTypeLabel(notif.type)}
                              </Badge>
                              <span className="text-[10px] md:text-xs text-muted-foreground">
                                {formatDateTime(notif.created_at, {
                                  day: "numeric",
                                  month: "short",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                            </div>
                            <p className={`text-xs md:text-sm ${!notif.is_read ? "font-semibold" : ""}`}>{notif.title}</p>
                            {notif.message && (
                              <p className="text-[10px] md:text-xs text-muted-foreground mt-1">{notif.message}</p>
                            )}
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleMarkRead(notif.notification_id)}
                            disabled={markingRead === notif.notification_id}
                            className="h-6 w-6 md:h-8 md:w-8 p-0"
                            title={notif.is_read ? "Означи како непрочитано" : "Означи како прочитано"}
                          >
                            {markingRead === notif.notification_id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : notif.is_read ? (
                              <Circle className="h-3 w-3 md:h-4 md:w-4" />
                            ) : (
                              <CheckCircle className="h-3 w-3 md:h-4 md:w-4 text-green-600" />
                            )}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                  {hasMoreNotifications && (
                    <div className="text-center pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleLoadMore}
                        disabled={loadingMore}
                        className="text-xs md:text-sm"
                      >
                        {loadingMore ? (
                          <><Loader2 className="h-3 w-3 animate-spin mr-2" />Се вчитува...</>
                        ) : (
                          <>Прикажи повеќе ({notifications.length} од {notificationsTotal})</>
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
