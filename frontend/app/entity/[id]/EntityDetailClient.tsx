"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Building2,
  FileText,
  TrendingUp,
  MapPin,
  Mail,
  Phone,
  Globe,
  User,
  ExternalLink,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import { formatCurrency, formatDate, tenderUrl } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Breadcrumb } from "@/components/Breadcrumb";
import { SignupGate } from "@/components/SignupGate";

const API_URL =
  typeof window !== "undefined"
    ? window.location.hostname === "localhost"
      ? "http://localhost:8000"
      : "https://api.nabavkidata.com"
    : "https://api.nabavkidata.com";

interface EntityData {
  entity_id: string;
  entity_name: string;
  entity_type?: string;
  category?: string;
  city?: string;
  total_tenders: number;
  total_value_mkd?: number;
  contact_person?: string;
  contact_email?: string;
  contact_phone?: string;
  website?: string;
  address?: string;
}

interface EntityTender {
  tender_id: string;
  title: string;
  status: string;
  estimated_value_mkd?: number;
  closing_date?: string;
  winner?: string;
}

export default function EntityDetailClient() {
  const params = useParams();
  const entityId = params?.id as string;
  const { user } = useAuth();

  const [entity, setEntity] = useState<EntityData | null>(null);
  const [tenders, setTenders] = useState<EntityTender[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!entityId) return;
    fetchEntity();
  }, [entityId]);

  async function fetchEntity() {
    setLoading(true);
    setError(null);
    try {
      const [entityRes, tendersRes] = await Promise.all([
        fetch(`${API_URL}/api/seo/entity/${encodeURIComponent(entityId)}`),
        fetch(`${API_URL}/api/seo/entity/${encodeURIComponent(entityId)}/tenders?limit=20`),
      ]);

      if (!entityRes.ok) throw new Error("Entity not found");

      const entityData = await entityRes.json();
      setEntity(entityData);

      if (tendersRes.ok) {
        const tendersData = await tendersRes.json();
        setTenders(tendersData.tenders || []);
      }
    } catch (err: any) {
      setError(err.message || "Грешка при вчитување");
    } finally {
      setLoading(false);
    }
  }

  function statusLabel(status: string) {
    switch (status) {
      case "open": return "Отворен";
      case "awarded": return "Доделен";
      case "cancelled": return "Поништен";
      default: return status;
    }
  }

  function statusColor(status: string) {
    switch (status) {
      case "open": return "bg-green-500";
      case "awarded": return "default";
      case "cancelled": return "bg-red-500";
      default: return "secondary";
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto py-8 px-4">
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center gap-2">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            <span>Се вчитува...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !entity) {
    return (
      <div className="container mx-auto py-8 px-4">
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-destructive mb-4">{error || "Институцијата не е пронајдена"}</p>
              <Link href="/tenders">
                <Button>
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Назад кон тендери
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4">
      <Breadcrumb
        items={[{ label: "Тендери", href: "/tenders" }]}
        currentPage={entity.entity_name}
      />

      <div className="mb-6">
        <h1 className="text-3xl font-bold">{entity.entity_name}</h1>
        <div className="flex flex-wrap items-center gap-2 mt-2 text-muted-foreground">
          {entity.entity_type && <Badge variant="outline">{entity.entity_type}</Badge>}
          {entity.category && <Badge variant="secondary">{entity.category}</Badge>}
          {entity.city && (
            <span className="flex items-center gap-1 text-sm">
              <MapPin className="h-3.5 w-3.5" /> {entity.city}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Вкупно тендери</p>
                <p className="text-2xl font-bold">{entity.total_tenders}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <TrendingUp className="h-8 w-8 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Вкупна вредност</p>
                {user ? (
                  <p className="text-xl font-bold">{formatCurrency(entity.total_value_mkd)}</p>
                ) : (
                  <p className="text-sm font-medium text-blue-600">Бесплатна регистрација</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Building2 className="h-8 w-8 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Тип</p>
                <p className="text-lg font-semibold">{entity.entity_type || "Н/А"}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Teaser Insights — visible to everyone */}
      <Card className="mb-6 border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30">
        <CardContent className="py-5">
          <h2 className="font-semibold text-lg mb-3">Клучни увиди</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            {entity.total_tenders > 0 && (
              <div className="flex items-start gap-2">
                <FileText className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
                <span>
                  Објавила <strong>{entity.total_tenders} тендери</strong> на платформата за е-набавки
                </span>
              </div>
            )}
            {entity.total_value_mkd != null && entity.total_value_mkd > 0 && (
              <div className="flex items-start gap-2">
                <TrendingUp className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                <span>
                  Вкупна вредност на набавки: {user ? <strong>{formatCurrency(entity.total_value_mkd)}</strong> : <strong className="text-blue-600">регистрирајте се</strong>}
                </span>
              </div>
            )}
            {entity.city && (
              <div className="flex items-start gap-2">
                <MapPin className="h-4 w-4 text-purple-500 mt-0.5 shrink-0" />
                <span>
                  Локација: <strong>{entity.city}</strong>
                </span>
              </div>
            )}
            {entity.total_tenders > 0 && entity.total_value_mkd != null && entity.total_value_mkd > 0 && (
              <div className="flex items-start gap-2">
                <Building2 className="h-4 w-4 text-orange-500 mt-0.5 shrink-0" />
                <span>
                  Просечна вредност по тендер: {user ? <strong>{formatCurrency(entity.total_value_mkd / entity.total_tenders)}</strong> : <strong className="text-blue-600">регистрирајте се</strong>}
                </span>
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            Регистрирајте се за контакт информации, листа на тендери, победници и детална анализа.
          </p>
        </CardContent>
      </Card>

      {/* Tender titles — visible to everyone (no values shown) */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Последни тендери ({tenders.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {tenders.length === 0 ? (
            <p className="text-muted-foreground text-sm py-4">Нема пронајдени тендери.</p>
          ) : (
            <div className="space-y-3">
              {tenders.slice(0, 5).map((t) => (
                <div
                  key={t.tender_id}
                  className="p-4 rounded-lg border"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-sm line-clamp-2">{t.title}</h3>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        {t.closing_date && <span>Рок: {formatDate(t.closing_date)}</span>}
                      </div>
                    </div>
                    <Badge
                      className={
                        t.status === "open"
                          ? "bg-green-500 text-white"
                          : t.status === "awarded"
                          ? ""
                          : "bg-red-500 text-white"
                      }
                      variant={t.status === "awarded" ? "default" : "secondary"}
                    >
                      {statusLabel(t.status)}
                    </Badge>
                  </div>
                </div>
              ))}
              {tenders.length > 5 && (
                <p className="text-sm text-muted-foreground text-center py-2">
                  + уште {tenders.length - 5} тендери — регистрирајте се за целосен преглед
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Gated: contact info + full tender links with values */}
      <SignupGate message="Регистрирајте се за контакт информации, вредности на тендери и победници">
      {(entity.contact_email || entity.contact_phone || entity.website || entity.address) && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              Контакт информации
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {entity.address && (
              <div className="flex items-start gap-2">
                <MapPin className="h-4 w-4 mt-1 text-muted-foreground" />
                <span>{entity.address}</span>
              </div>
            )}
            {entity.contact_person && (
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <span>{entity.contact_person}</span>
              </div>
            )}
            {entity.contact_email && (
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <a href={`mailto:${entity.contact_email}`} className="hover:text-primary">
                  {entity.contact_email}
                </a>
              </div>
            )}
            {entity.contact_phone && (
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-muted-foreground" />
                <span>{entity.contact_phone}</span>
              </div>
            )}
            {entity.website && (
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-muted-foreground" />
                <a href={entity.website} target="_blank" rel="noopener noreferrer" className="hover:text-primary flex items-center gap-1">
                  {entity.website} <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
          </CardContent>
        </Card>
      )}
      </SignupGate>
    </div>
  );
}
