"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { HelpCircle, LogIn, Mail, MessageSquare, FileText, Send, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type ConciergeFooter, type ConciergeSource } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canAccessPortal, hasClientPerks } from "@/lib/portal";

const EMAIL = "hello@nabavkidata.com";
const MAX_QUESTION_CHARS = 1000;
const HISTORY_MSGS = 6;

const PANEL_SUGGESTIONS = [
  "За што е овој тендер?",
  "Кој е крајниот рок?",
  "Кои документи се прикачени?",
  "Дали бараат ISO сертификат?",
];

const PAGE_SUGGESTIONS = [
  "Најди отворени тендери за софтвер",
  "Како се поднесува понуда на е-набавки?",
  "Како функционира вашата услуга?",
  "Што е е-аукција?",
];

interface ConciergeMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  footer?: ConciergeFooter;
  sources?: ConciergeSource[];
}

interface ConciergeChatProps {
  tenderId?: string;
  tenderTitle?: string;
  variant?: "page" | "panel";
}

function orderUrl(tenderId?: string): string {
  return "/usluga?src=concierge" + (tenderId ? `&tender=${encodeURIComponent(tenderId)}` : "");
}

function storageKey(userId: string | undefined, tenderId?: string): string {
  // Scoped per user so a different login in the same tab never sees (or sends
  // as history) the previous user's conversation.
  return `concierge:${userId || "anon"}:${tenderId || "global"}`;
}

function loadStored(key: string): ConciergeMessage[] {
  try {
    const raw = window.sessionStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveStored(key: string, messages: ConciergeMessage[]) {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(messages.slice(-40)));
  } catch {
    // storage unavailable (private mode, quota): the chat still works in memory
  }
}

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function FooterButtons({ footer, tenderId }: { footer: ConciergeFooter; tenderId?: string }) {
  const subject = encodeURIComponent("Прашање за тендер " + (tenderId ?? ""));
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {footer.messages_url && (
        <Button asChild variant="outline" size="sm" className="h-7 text-xs gap-1.5">
          <Link href={footer.messages_url}>
            <MessageSquare className="h-3.5 w-3.5" />
            Пораки
          </Link>
        </Button>
      )}
      <Button asChild variant="outline" size="sm" className="h-7 text-xs gap-1.5">
        <a href={`mailto:${footer.email}?subject=${subject}`}>
          <Mail className="h-3.5 w-3.5" />
          Е-пошта
        </a>
      </Button>
      {footer.order_url && (
        <Button asChild variant="outline" size="sm" className="h-7 text-xs gap-1.5">
          <Link href={footer.order_url}>
            <FileText className="h-3.5 w-3.5" />
            Нарачајте понуда
          </Link>
        </Button>
      )}
    </div>
  );
}

export function ConciergeChat({ tenderId, tenderTitle, variant = "page" }: ConciergeChatProps) {
  const { user, isLoading: authLoading } = useAuth();
  const pathname = usePathname();
  const isPanel = variant === "panel";
  const key = storageKey(user?.user_id, tenderId);
  const perks = hasClientPerks(user);

  const [messages, setMessages] = useState<ConciergeMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [dailyLimit, setDailyLimit] = useState<number | null>(null);
  const [statusFooter, setStatusFooter] = useState<ConciergeFooter | null>(null);
  const [loginHref, setLoginHref] = useState("/auth/login");
  const endRef = useRef<HTMLDivElement>(null);

  // Footer used for local bubbles (errors) until the server sent one.
  const fallbackFooter: ConciergeFooter = statusFooter ?? {
    messages_url: canAccessPortal(user) ? "/portal/messages" : null,
    email: EMAIL,
    order_url: perks ? null : orderUrl(tenderId),
  };

  useEffect(() => {
    try {
      const search = typeof window !== "undefined" ? window.location.search : "";
      setLoginHref(`/auth/login?redirect=${encodeURIComponent((pathname || "/") + search)}`);
    } catch {
      setLoginHref("/auth/login");
    }
  }, [pathname]);

  // Restore this conversation from sessionStorage.
  useEffect(() => {
    if (!user) {
      setMessages([]);
      return;
    }
    setMessages(loadStored(key));
  }, [key, user]);

  useEffect(() => {
    if (!user) return;
    saveStored(key, messages);
  }, [key, messages, user]);

  const refreshStatus = useCallback(() => {
    let cancelled = false;
    api
      .getConciergeStatus()
      .then((s) => {
        if (cancelled) return;
        setRemaining(s.remaining_today);
        setDailyLimit(s.daily_limit);
        setStatusFooter(s.footer);
      })
      .catch(() => {
        // Status is informative only; asking still works.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!user) return;
    return refreshStatus();
  }, [user, refreshStatus]);

  useEffect(() => {
    if (messages.length > 0) endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, sending]);

  const limitReached = !perks && remaining !== null && remaining <= 0;

  // The daily counter resets at Skopje midnight: re-check when the tab regains
  // focus so an open tab does not stay locked after the reset.
  useEffect(() => {
    if (!user || !limitReached) return;
    const onWake = () => {
      if (typeof document === "undefined" || document.visibilityState === "visible") refreshStatus();
    };
    window.addEventListener("focus", onWake);
    document.addEventListener("visibilitychange", onWake);
    return () => {
      window.removeEventListener("focus", onWake);
      document.removeEventListener("visibilitychange", onWake);
    };
  }, [user, limitReached, refreshStatus]);

  const send = useCallback(
    async (raw: string) => {
      const question = raw.trim().slice(0, MAX_QUESTION_CHARS);
      if (!question || sending || limitReached) return;

      const history = messages
        .slice(-HISTORY_MSGS)
        .map((m) => ({ role: m.role, content: m.content }));
      const userMsg: ConciergeMessage = { id: newId(), role: "user", content: question };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setSending(true);

      try {
        const res = await api.askConcierge({
          question,
          tender_id: tenderId,
          history,
          page: isPanel ? "tender" : "chat",
        });
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: res.answer,
            footer: res.footer,
            sources: res.sources,
          },
        ]);
        setStatusFooter(res.footer);
        setRemaining(res.remaining_today);
        setDailyLimit(res.daily_limit);
      } catch (err: any) {
        const msg = String(err?.message || "");
        const unauthorized = err?.status === 401 || /unauthori[sz]ed|authentication failed/i.test(msg);
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: unauthorized
              ? "Сесијата истече. Најавете се повторно."
              : "Грешка при добивање одговор. Обидете се повторно.",
            footer: fallbackFooter,
          },
        ]);
      } finally {
        setSending(false);
      }
    },
    // fallbackFooter is derived from statusFooter/user/tenderId
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [messages, sending, limitReached, tenderId, isPanel, statusFooter, user]
  );

  const shell = isPanel ? "" : "flex flex-col h-full";

  // Anonymous: no request is ever sent.
  if (!authLoading && !user) {
    return (
      <Card className="p-4 md:p-5">
        <div className="flex items-start gap-3">
          <HelpCircle className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
          <div className="space-y-3">
            <p className="text-sm">Најавете се за да поставите прашање за тендерите.</p>
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm" className="gap-1.5">
                <Link href={loginHref}>
                  <LogIn className="h-4 w-4" />
                  Најавете се
                </Link>
              </Button>
              <Button asChild size="sm" variant="outline" className="gap-1.5">
                <Link href={orderUrl(tenderId)}>
                  <FileText className="h-4 w-4" />
                  Нарачајте понуда
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  if (authLoading) {
    return (
      <Card className="p-4 flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </Card>
    );
  }

  const suggestions = isPanel ? PANEL_SUGGESTIONS : PAGE_SUGGESTIONS;

  return (
    <Card className={`${shell} ${isPanel ? "p-4" : "p-3 md:p-4"}`}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b">
        <div className="flex items-center gap-2 min-w-0">
          <HelpCircle className="h-4 w-4 text-primary flex-shrink-0" />
          <span className="text-sm font-medium truncate">
            {isPanel ? "Прашања за тендерот" : "Прашања за тендери"}
          </span>
        </div>
        {!perks && remaining !== null && dailyLimit !== null && (
          <span className="text-xs text-muted-foreground">
            Остануваат {remaining} од {dailyLimit} прашања денес
          </span>
        )}
      </div>

      {/* Messages */}
      <div
        className={`overflow-y-auto py-3 space-y-4 ${isPanel ? "max-h-[420px] min-h-[120px]" : "flex-1 min-h-0"}`}
      >
        {messages.length === 0 ? (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              {isPanel && tenderTitle
                ? `Прашајте за „${tenderTitle}“.`
                : "Поставете кратко прашање за тендерите или за постапката."}
            </p>
            <div className={`grid gap-2 ${isPanel ? "sm:grid-cols-2" : "sm:grid-cols-2"}`}>
              {suggestions.map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled={sending || limitReached}
                  onClick={() => send(q)}
                  className="text-left text-xs md:text-sm rounded-md border px-3 py-2 hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="flex justify-end">
                <div className="max-w-[85%] rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm whitespace-pre-wrap break-words">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={m.id} className="flex justify-start">
                <div className="max-w-[90%] w-full">
                  <div className="rounded-lg bg-muted px-3 py-2 text-sm whitespace-pre-wrap break-words">
                    {m.content}
                  </div>
                  {m.sources && m.sources.some((s) => s.type === "tender") && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {m.sources
                        .filter((s): s is Extract<ConciergeSource, { type: "tender" }> => s.type === "tender")
                        .map((s) => (
                          <Link
                            key={s.tender_id}
                            href={s.url}
                            className="inline-flex max-w-full items-center rounded-full border px-2 py-0.5 text-xs hover:bg-accent truncate"
                          >
                            <span className="truncate">
                              {s.tender_id}
                              {s.title ? ` – ${s.title}` : ""}
                            </span>
                          </Link>
                        ))}
                    </div>
                  )}
                  {m.footer && <FooterButtons footer={m.footer} tenderId={tenderId} />}
                </div>
              </div>
            )
          )
        )}
        {sending && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Одговара...
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Limit reached */}
      {limitReached && (
        <div className="rounded-md border px-3 py-2 mb-2">
          <p className="text-xs">Ги искористивте прашањата за денес.</p>
          <FooterButtons footer={fallbackFooter} tenderId={tenderId} />
        </div>
      )}

      {/* Input */}
      <div className="pt-3 border-t">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={MAX_QUESTION_CHARS}
            placeholder={limitReached ? "Ги искористивте прашањата за денес." : "Поставете прашање..."}
            disabled={sending || limitReached}
            className="flex-1"
            aria-label="Прашање"
          />
          <Button type="submit" disabled={sending || limitReached || !input.trim()} aria-label="Испрати">
            <Send className="h-4 w-4" />
          </Button>
        </form>
        <p className="text-[11px] text-muted-foreground mt-2">
          AI асистентот дава само основни информации од нашата база. Понудите ги подготвува нашиот тим.
        </p>
      </div>
    </Card>
  );
}

export default ConciergeChat;
