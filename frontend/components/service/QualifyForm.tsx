"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CheckCircle2, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface QualifyFormProps {
  /** tenders.tender_id when the request is about one tender */
  tenderId?: string | null;
  /** where the request came from: usluga | tender_card | paywall | digest */
  source?: string;
  /** compact = company + email only (tender card) */
  compact?: boolean;
}

/**
 * The one front door of the bid-writing service.
 * Posts to /api/bid-service/qualify. The API never logs anyone in: a brand-new
 * email gets an unverified prospect account plus an emailed set-password link
 * (which verifies the address); an existing email is captured against that
 * account. Either way the visitor sees the confirmation in place.
 */
export default function QualifyForm({ tenderId, source = "usluga", compact = false }: QualifyFormProps) {
  const { user } = useAuth();
  const [company, setCompany] = useState(user?.company_name || "");
  const [email, setEmail] = useState(user?.email || "");
  const [person, setPerson] = useState(user?.full_name || "");
  const [phone, setPhone] = useState("");
  const [wants, setWants] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  // AuthProvider loads the profile after mount: fill any still-empty fields
  // so a signed-in user's request is linked to their own account.
  useEffect(() => {
    if (!user) return;
    setCompany((v) => v || user.company_name || "");
    setEmail((v) => v || user.email || "");
    setPerson((v) => v || user.full_name || "");
  }, [user]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.submitBidRequest({
        company: company.trim(),
        email: email.trim(),
        lead_person: person.trim(),
        phone: phone.trim(),
        wants_to_win: wants.trim(),
        tender_id: tenderId || null,
        source,
      });
      setDone(res.message);
    } catch (err: any) {
      setError(err?.message || "Барањето не успеа. Обидете се повторно.");
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-green-500/30 bg-green-500/10 p-4">
        <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
        <div className="text-sm">
          <p className="font-medium text-foreground">Барањето е примено</p>
          <p className="text-muted-foreground mt-1">{done}</p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="q-company">Компанија</Label>
        <Input
          id="q-company"
          required
          minLength={2}
          placeholder="Име на фирмата"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="q-email">Е-пошта</Label>
        <Input
          id="q-email"
          type="email"
          required
          placeholder="vie@firma.mk"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      {!compact && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="q-person">Име и презиме</Label>
              <Input id="q-person" value={person} onChange={(e) => setPerson(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="q-phone">Телефон</Label>
              <Input id="q-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="q-wants">Какви тендери сакате да добиете?</Label>
            <Textarea
              id="q-wants"
              rows={3}
              placeholder="На пр. одржување на софтвер, градежни работи, медицински материјал, или број на конкретен тендер"
              value={wants}
              onChange={(e) => setWants(e.target.value)}
            />
          </div>
        </>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : tenderId ? "Напишете ја оваа понуда за мене" : "Побарајте бесплатна проценка"}
      </Button>
      <p className="text-xs text-muted-foreground text-center">
        Одговараме во рок од еден работен ден. Проценката е бесплатна.
      </p>
    </form>
  );
}
