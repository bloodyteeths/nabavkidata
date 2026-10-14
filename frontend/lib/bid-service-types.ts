// Types and constants for the done-for-you bid service (Phase 2, Oct 2026).
// Interfaces mirror backend/api/bid_jobs.py response shapes (contract §3.3).

export type BidJobStatus =
  | 'requested'
  | 'payment_required'
  | 'preparing'
  | 'ready'
  | 'changes_requested'
  | 'approved'
  | 'submitted'
  | 'won'
  | 'lost'
  | 'cancelled';
export type BidOutcome = 'won' | 'lost' | 'cancelled';
export type WhoseMove = 'client' | 'us' | 'none';
export type DeadlineState = 'ok' | 'soon' | 'today' | 'passed';
export type BidFileKind = 'tehnicka' | 'finansiska' | 'izjava' | 'checklist' | 'drugo';
export type FileApprovalStatus = 'pending' | 'approved' | 'changes_requested';
export type ClientDocumentCategory =
  | 'tekovna_sostojba'
  | 'danocno_uverenie'
  | 'ddv_registracija'
  | 'kazneno_potvrda'
  | 'iso_sertifikat'
  | 'drug_sertifikat'
  | 'referenca'
  | 'boni_finansiski'
  | 'cv_personal'
  | 'drugo';
export type AccountType = 'free' | 'prospect' | 'managed_client';

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

export interface TenderSummary {
  tender_id: string;
  title: string | null;
  procuring_entity: string | null;
  closing_date: string | null;
  estimated_value_mkd: number | null;
  status: string | null;
}

export interface BidJobSummary {
  id: string;
  tender_id: string;
  tender_title: string | null;
  procuring_entity: string | null;
  closing_date: string | null;
  estimated_value_mkd: number | null;
  status: BidJobStatus;
  outcome: BidOutcome | null;
  phase_text: string;
  whose_move: WhoseMove;
  days_left: number | null;
  deadline_state: DeadlineState | null;
  prep_fee_mkd: number | null;
  free: boolean;
  unread_messages: number;
  files_pending_review: number;
  created_at: string;
  updated_at: string;
}

export interface BidJobDetail extends BidJobSummary {
  success_fee_pct: number | null;
  invoice_number: string | null;
  invoice_issued_at: string | null;
  paid_at: string | null;
  published_at: string | null;
  approved_at: string | null;
  submitted_at: string | null;
  outcome_at: string | null;
  cancelled_at: string | null;
  cancelled_by: 'client' | 'admin' | null;
  cancel_reason: string | null;
  client_note: string | null;
  can_cancel: boolean;
  can_mark_submitted: boolean;
  can_approve_all: boolean;
}

export interface AdminBidJobSummary extends BidJobSummary {
  user_id: string;
  user_email: string;
  company_name: string | null;
  assigned_to: string | null;
  assigned_to_email: string | null;
  invoice_number: string | null;
  paid_at: string | null;
  publish_count: number;
}

export interface AdminBidJobDetail extends BidJobDetail {
  user_id: string;
  user_email: string;
  company_name: string | null;
  assigned_to: string | null;
  assigned_to_email: string | null;
  publish_count: number;
  admin_notes: string | null;
  reopen_count: number;
  paid_via: PaidVia | null;
  /** Why publishing is blocked (success fee not authorised), or null. */
  publish_blocked_reason: string | null;
}

export interface BidFile {
  id: string;
  kind: BidFileKind;
  title: string;
  original_name: string;
  mime: string | null;
  size_bytes: number;
  approval_status: FileApprovalStatus;
  client_comment: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface AdminBidFile extends BidFile {
  client_visible: boolean;
  updated_at: string;
}

export interface BidMessage {
  id: string;
  job_id: string | null;
  sender_role: 'client' | 'admin';
  sender_name: string | null;
  body: string;
  created_at: string;
  read_by_client_at: string | null;
  read_by_admin_at: string | null;
}

export interface PaymentInfo {
  required: boolean;
  free: boolean;
  prep_fee_mkd: number | null;
  success_fee_pct: number | null;
  invoice_number: string | null;
  invoice_issued_at: string | null;
  paid_at: string | null;
  /** Original name of the invoice PDF the admin attached, or null. */
  invoice_file_name: string | null;
  /** How the prep fee was settled (Phase 2b). */
  paid_via: PaidVia | null;
  /** Set once the client chose „Платам со фактура“. */
  invoice_requested_at: string | null;
  /** True while the client can pay the prep fee by card (Stripe Checkout). */
  can_pay_card: boolean;
  /** Success fee for this bid once a win is confirmed; null before that. */
  success_fee: SuccessFeeInfo | null;
}

export type PaidVia = 'stripe' | 'invoice' | 'free';

export interface SuccessFeeInfo {
  status: 'confirmed' | 'invoiced';
  fee_mkd: number | null;
  first_year_value_mkd: number | null;
  charge_not_before: string | null;
  /** True when a Stripe draft invoice exists (charged to the saved card). */
  stripe: boolean;
}

/** GET /api/bid-service/billing/status and POST /billing/setup-complete. */
export interface BillingStatus {
  has_card: boolean;
  card_brand: string | null;
  card_last4: string | null;
  terms_accepted: boolean;
  current_version: string;
  success_fee_pct: number | null;
  success_fee_authorised: boolean;
  success_fee_authorised_at: string | null;
  success_fee_authorised_via: 'card' | 'offline' | null;
  card_payments_enabled: boolean;
}

export interface PrepPaymentCompleteResponse {
  paid: boolean;
  reason: string | null;
  account_promoted: boolean;
  job: BidJobDetail;
  payment: PaymentInfo;
}

export interface ChooseInvoiceResponse {
  job: BidJobDetail;
  payment: PaymentInfo;
}

export type ClientWinStatus = 'suspected' | 'confirmed' | 'dismissed' | 'invoiced';

export interface ClientWin {
  id: string;
  job_id: string | null;
  user_id: string;
  email: string;
  company_name: string | null;
  tender_id: string;
  tender_title: string | null;
  procuring_entity: string | null;
  matched_name: string | null;
  match_score: number | null;
  contract_value_mkd: number | null;
  value_source: 'bid' | 'actual' | 'estimated' | 'admin' | null;
  contract_months: number | null;
  first_year_value_mkd: number | null;
  success_fee_pct: number | null;
  prep_fee_credit_mkd: number;
  success_fee_mkd: number | null;
  status: ClientWinStatus;
  detected_at: string;
  confirmed_at: string | null;
  notice_sent_at: string | null;
  charge_not_before: string | null;
  stripe_invoice_id: string | null;
  invoice_number: string | null;
  invoiced_at: string | null;
  notes: string | null;
  has_card: boolean;
}

export interface AdminWinsResponse {
  wins: ClientWin[];
  summary: {
    suspected: number;
    confirmed: number;
    invoiced: number;
    dismissed: number;
    pipeline_fee_mkd: number;
    confirmed_fee_mkd: number;
  };
}

export interface ConfirmWinBody {
  first_year_value_mkd?: number;
  success_fee_mkd?: number;
  notes?: string;
  create_stripe_invoice?: boolean;
}

/** The 7-day notice: charge_not_before is set only once the email went out. */
export interface WinNoticeResult {
  sent: boolean;
  message: string;
}

export interface ConfirmWinResponse {
  win: ClientWin;
  invoice: { created: boolean; stripe_invoice_id: string | null; message: string };
  notice: WinNoticeResult;
}

export interface ClientDocument {
  id: string;
  category: ClientDocumentCategory;
  title: string;
  original_name: string;
  mime: string | null;
  size_bytes: number;
  expires_on: string | null;
  expired: boolean;
  expires_soon: boolean;
  uploaded_by_role: 'client' | 'admin';
  created_at: string;
  updated_at: string;
}

export interface MatchedTender {
  tender_id: string;
  title: string | null;
  procuring_entity: string | null;
  closing_date: string | null;
  estimated_value_mkd: number | null;
  match_score: number;
  match_reasons: string[];
  matched_at: string;
}

export interface DeadlineItem {
  date: string;
  kind: 'job' | 'matched';
  job_id: string | null;
  tender_id: string;
  title: string | null;
  procuring_entity: string | null;
  status: BidJobStatus | null;
}

export interface CalendarTokenResponse {
  token: string;
  url: string;
  webcal_url: string;
}

export interface PortalSummary {
  account_type: AccountType;
  company_name: string | null;
  your_move: BidJobSummary[];
  active_jobs: BidJobSummary[];
  counts: { your_move: number; active: number; total: number };
  unread_messages: number;
  unread_general: number;
  matched_tenders: MatchedTender[];
  first_run: boolean;
}

export interface AdminBidSummary {
  counts: Record<BidJobStatus, number>;
  needs_us: number;
  needs_client: number;
  overdue: number;
  unread_messages: number;
}

export interface AdminClientInfo {
  user_id: string;
  email: string;
  full_name: string | null;
  company_name: string | null;
  account_type: AccountType;
  free_drafting: boolean;
  prep_fee_mkd: number;
  success_fee_pct: number;
  terms_agreed_at: string | null;
  agreement_version: string | null;
  has_card: boolean;
  card_brand: string | null;
  card_last4: string | null;
  success_fee_authorised_at: string | null;
  success_fee_authorised_via: 'card' | 'offline' | null;
  success_fee_authorised_ref: string | null;
}

/** The client's own fees and whether the current service terms are accepted. */
export interface BidAgreement {
  prep_fee_mkd: number | null;
  success_fee_pct: number | null;
  free_drafting: boolean;
  terms_agreed_at: string | null;
  agreement_version: string | null;
  current_version: string;
  accepted: boolean;
}

export interface PortalUnread {
  unread_messages: number;
  unread_general: number;
  unread_jobs: number;
}

export interface BidJobEvent {
  event: string;
  kind: 'audit' | 'notify';
  actor_role: 'client' | 'admin' | 'system' | null;
  created_at: string;
  detail: Record<string, unknown> | null;
}

export interface AdminInboxThread {
  user_id: string;
  user_email: string;
  company_name: string | null;
  job_id: string | null;
  tender_id: string | null;
  tender_title: string | null;
  last_message_at: string;
  last_body: string;
  last_sender_role: 'client' | 'admin';
  unread_count: number;
}

export interface AdminInboxResponse {
  threads: AdminInboxThread[];
  total_unread: number;
}

export interface AdminTeamMember {
  user_id: string;
  email: string;
  full_name: string | null;
}

// ---------------------------------------------------------------------------
// Response wrappers
// ---------------------------------------------------------------------------

export interface BeginBidJobResponse {
  job: BidJobSummary;
  created: boolean;
  /** True when the job waits at the fee gate (status payment_required). */
  payment_required: boolean;
}

export interface BidJobDetailResponse {
  job: BidJobDetail;
  tender: TenderSummary;
  files: BidFile[];
  messages: BidMessage[];
  payment: PaymentInfo;
}

export interface FileActionResponse {
  file: BidFile;
  job: BidJobSummary;
}

export interface JobActionResponse {
  job: BidJobSummary;
}

export interface AdminJobActionResponse {
  job: AdminBidJobSummary;
  account_promoted?: boolean;
  /** Set by POST /admin/jobs: false when the client already had a job for the tender. */
  created?: boolean;
}

export interface AdminBidJobsResponse {
  jobs: AdminBidJobSummary[];
  total: number;
  summary: AdminBidSummary;
}

export interface AdminBidJobDetailResponse {
  job: AdminBidJobDetail;
  tender: TenderSummary;
  files: AdminBidFile[];
  messages: BidMessage[];
  client: AdminClientInfo;
  client_documents: ClientDocument[];
  events: BidJobEvent[];
  payment: PaymentInfo;
}

export interface AdminBidJobFilters {
  status?: BidJobStatus | 'open' | 'needs_us' | 'needs_client' | 'all';
  assigned_to?: string;
  user_id?: string;
  q?: string;
  limit?: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const BID_STATUS_LABELS: Record<BidJobStatus, string> = {
  requested: 'Барањето е примено',
  payment_required: 'Чекаме уплата',
  preparing: 'Во подготовка',
  ready: 'Готова за преглед',
  changes_requested: 'Измени во тек',
  approved: 'Одобрена',
  submitted: 'Поднесена',
  won: 'Добиена',
  lost: 'Не е добиена',
  cancelled: 'Откажана',
};

export const BID_STATUS_WHOSE_MOVE: Record<BidJobStatus, WhoseMove> = {
  requested: 'us',
  payment_required: 'client',
  preparing: 'us',
  ready: 'client',
  changes_requested: 'us',
  approved: 'client',
  submitted: 'none',
  won: 'none',
  lost: 'none',
  cancelled: 'none',
};

export const WHOSE_MOVE_LABELS: Record<WhoseMove, string> = {
  client: 'Ваш потег',
  us: 'Ние работиме',
  none: '',
};

const BADGE_AMBER = 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30';
const BADGE_BLUE = 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-500/15 dark:text-blue-300 dark:border-blue-500/30';
const BADGE_INDIGO = 'bg-indigo-100 text-indigo-800 border-indigo-200 dark:bg-indigo-500/15 dark:text-indigo-300 dark:border-indigo-500/30';
const BADGE_GREEN = 'bg-green-100 text-green-800 border-green-200 dark:bg-green-500/15 dark:text-green-300 dark:border-green-500/30';
const BADGE_SLATE = 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-500/15 dark:text-slate-300 dark:border-slate-500/30';

export const BID_STATUS_BADGE_CLASS: Record<BidJobStatus, string> = {
  requested: BADGE_BLUE,
  payment_required: BADGE_AMBER,
  preparing: BADGE_BLUE,
  ready: BADGE_AMBER,
  changes_requested: BADGE_BLUE,
  approved: BADGE_AMBER,
  submitted: BADGE_INDIGO,
  won: BADGE_GREEN,
  lost: BADGE_SLATE,
  cancelled: BADGE_SLATE,
};

export const PRE_SUBMITTED_STATUSES: BidJobStatus[] = [
  'requested',
  'payment_required',
  'preparing',
  'ready',
  'changes_requested',
  'approved',
];

export const TERMINAL_STATUSES: BidJobStatus[] = ['won', 'lost', 'cancelled'];

export const BID_FILE_KIND_LABELS: Record<BidFileKind, string> = {
  tehnicka: 'Техничка понуда',
  finansiska: 'Финансиска понуда',
  izjava: 'Изјава',
  checklist: 'Листа за проверка',
  drugo: 'Друго',
};

export const FILE_APPROVAL_LABELS: Record<FileApprovalStatus, string> = {
  pending: 'Чека преглед',
  approved: 'Одобрено',
  changes_requested: 'Побарани измени',
};

export const CLIENT_DOCUMENT_CATEGORIES: ClientDocumentCategory[] = [
  'tekovna_sostojba',
  'danocno_uverenie',
  'ddv_registracija',
  'kazneno_potvrda',
  'iso_sertifikat',
  'drug_sertifikat',
  'referenca',
  'boni_finansiski',
  'cv_personal',
  'drugo',
];

export const CLIENT_DOCUMENT_CATEGORY_LABELS: Record<ClientDocumentCategory, string> = {
  tekovna_sostojba: 'Тековна состојба (ЦРМ)',
  danocno_uverenie: 'Даночно уверение / потврда за платени даноци',
  ddv_registracija: 'Решение за ДДВ регистрација',
  kazneno_potvrda: 'Потврда од казнена евиденција',
  iso_sertifikat: 'ISO сертификат',
  drug_sertifikat: 'Друг сертификат / лиценца',
  referenca: 'Референца / потврда за изведени работи',
  boni_finansiski: 'БОНИ / финансиски извештај',
  cv_personal: 'CV на персонал',
  drugo: 'Друго',
};

export const BID_FILE_ACCEPT = '.pdf,.doc,.docx,.xls,.xlsx,.zip,.jpg,.png,.p7s,.xml';
export const BID_FILE_MAX_BYTES = 25 * 1024 * 1024;

/** Detail code the API returns (409) when the client has not accepted the current terms. */
export const TERMS_REQUIRED = 'terms_required';

/** Detail code of the 409 the publish gate returns when the success fee is not authorised. */
export const SUCCESS_FEE_NOT_AUTHORISED = 'success_fee_not_authorised';

export const PAID_VIA_LABELS: Record<PaidVia, string> = {
  stripe: 'Картичка',
  invoice: 'Фактура',
  free: 'Бесплатно',
};

/**
 * Payee details shown with an issued invoice. The bank account comes from the
 * environment so it is never hardcoded wrongly; when it is not configured the
 * client is pointed to the invoice PDF, which always carries it.
 */
export const FAKTURINO_PAYEE = {
  name: 'Фактурино ДООЕЛ Велес',
  address: 'ул. Сараевска 37, 1400 Велес',
  edb: '4004026525934',
  bankAccount: process.env.NEXT_PUBLIC_FAKTURINO_BANK_ACCOUNT || null,
  bankName: process.env.NEXT_PUBLIC_FAKTURINO_BANK_NAME || null,
};

export const PAYMENT_NEXT_STEP =
  'Штом уплатата ќе пристигне на сметката, ја евидентираме (обично во рок од еден работен ден) и веднаш започнуваме со подготовка. Ќе добиете известување по е-пошта.';

export const PAYMENT_INSTRUCTIONS =
  'Надоместот за подготовка го плаќате со картичка (преку Stripe) или по фактура. За плаќање по фактура уплатата се врши на трансакциската сметка на Фактурино ДООЕЛ наведена во фактурата, а во целта на дознаката го наведувате бројот на фактурата. Износите се без ДДВ: Фактурино ДООЕЛ не е ДДВ обврзник.';

export const ENABAVKI_SUBMIT_REMINDER =
  'Понудата ја потпишувате со вашиот дигитален сертификат и ја поднесувате сами на e-nabavki.gov.mk пред рокот. Откако ќе ја поднесете, кликнете „Поднесено“.';

export function formatMkd(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString('mk-MK') + ' МКД';
}
