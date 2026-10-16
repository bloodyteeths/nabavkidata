// Operator focus system (Phase 4) — mirrors backend api/ops.py.

export type OpsFocusKind =
  | 'manual'
  | 'hot_signal'
  | 'client_message'
  | 'job_approved_deadline'
  | 'job_ready_deadline'
  | 'job_changes'
  | 'job_preparing_deadline'
  | 'job_preparing'
  | 'job_requested'
  | 'job_invoice'
  | 'job_payment_check'
  | 'job_checkout_abandoned'
  | 'win_review'
  | 'lead_untriaged'
  | 'goback'
  | 'shortlist_curate'
  | 'client_touch';

export type OpsFocusGroup = 'clients' | 'sales' | 'money' | 'reminders';

export interface OpsLink {
  label: string;
  href: string;
}

export interface OpsDraft {
  to: string;
  subject: string;
  body_text: string;
}

export interface OpsFocusTender {
  tender_id: string;
  title: string;
  procuring_entity: string | null;
  closing_date: string | null;
  estimated_value_mkd: number | null;
}

export interface OpsFocusItem {
  key: string;
  kind: OpsFocusKind;
  group: OpsFocusGroup;
  priority: number;
  date: string;
  title: string;
  detail: string;
  email: string | null;
  tender: OpsFocusTender | null;
  links: OpsLink[];
  draft: OpsDraft | null;
  meta: Record<string, unknown>;
}

export interface OpsFocusResponse {
  date: string;
  off_day: boolean;
  items: OpsFocusItem[];
  done: OpsFocusItem[];
  notes: string[];
  counts: { total: number; by_group: Record<OpsFocusGroup, number> };
}

export interface OpsDraftSendBody {
  subject: string;
  body_text: string;
  force?: boolean;
}

export interface OpsDraftSendResponse {
  key: string;
  sent: boolean;
  message_id: string | null;
  to: string;
}

export interface OpsShortlistItem {
  tender_id: string;
  title: string;
  procuring_entity: string | null;
  closing_date: string | null;
  estimated_value_mkd: number | null;
  reason: string | null;
  rank: number;
  picked: boolean;
  note: string | null;
  open: boolean;
}

export interface OpsShortlist {
  id: string;
  user_id: string;
  email: string;
  company_name: string | null;
  account_type: string;
  status: 'draft' | 'sent' | 'skipped';
  subject: string;
  intro_text: string;
  built_at: string;
  sent_at: string | null;
  items: OpsShortlistItem[];
}

export interface OpsShortlistsResponse {
  week_start: string;
  shortlists: OpsShortlist[];
}

export interface OpsShortlistUpdateBody {
  subject?: string;
  intro_text?: string;
  picked: string[];
  notes?: Record<string, string>;
}

export interface OpsShortlistPreview {
  to: string;
  subject: string;
  body_text: string;
  body_html: string;
  violations: string[];
}

export interface OpsCalendarUrl {
  https_url: string;
  webcal_url: string;
}

export const OPS_GROUP_LABELS: Record<OpsFocusGroup, string> = {
  clients: 'Клиенти',
  sales: 'Продажба',
  money: 'Наплата',
  reminders: 'Потсетници',
};

export const OPS_GROUP_ORDER: OpsFocusGroup[] = ['clients', 'sales', 'money', 'reminders'];

export const OPS_REPLY_CC = 'atillatkulu@gmail.com';

/** Human labels for draft-copy violation codes returned by the backend checker. */
export const OPS_VIOLATION_LABELS: Record<string, string> = {
  price: 'спомнува цена или износ',
  free: 'спомнува „бесплатно“',
  call_promise: 'ветува телефонски повик',
  emoji: 'содржи емоџи',
  informal: 'неформално обраќање (ти)',
  latin_body: 'премногу латиница',
};
