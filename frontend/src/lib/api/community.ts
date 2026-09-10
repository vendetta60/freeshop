import { qs, request } from '@/lib/api/client';
import type { Paged, ProductCard } from '@/lib/api/catalogue';

/**
 * Location, needs, messaging, lending, aid and notifications.
 *
 * ONE module rather than six. They are six domains on the server, but on the
 * client they are one thing - the community layer - and they share the
 * `Location` type, the distance formatting and the query-key namespace.
 * Splitting them would mean six files that all import each other.
 *
 * These types mirror the backend schemas. `npm run gen:api` replaces them
 * with generated ones; keeping the names identical means that swap touches
 * only this file (same contract as lib/api/catalogue.ts).
 */

// ---------------------------------------------------------------------------
// Location
// ---------------------------------------------------------------------------
/**
 * A place as the API returns it.
 *
 * There is no latitude and no longitude here, and that is the contract, not
 * an omission: the server resolves a city or district to its CENTRE and
 * never publishes coordinates (backend app/schemas/location.py).
 */
export type Location = {
  country: string;
  region: string | null;
  city: string | null;
  district: string | null;
  label: string | null;
  /** Rounded server-side; only present when the request had an origin. */
  distance_km: number | null;
};

export type OwnLocation = Location & {
  /** 'none' | 'city' | 'district' - how precisely the place resolved. */
  precision: string;
};

export type LocationPayload = {
  city?: string | null;
  district?: string | null;
};

export type Places = {
  cities: { name: string; region: string }[];
  districts: Record<string, string[]>;
};

export const locationApi = {
  places: (signal?: AbortSignal) => request<Places>('/meta/places', { signal }),

  radiusOptions: (signal?: AbortSignal) =>
    request<{ radius_km: number[] }>('/meta/radius-options', { signal }),

  mine: (signal?: AbortSignal) => request<OwnLocation>('/users/me/location', { signal }),

  save: (payload: LocationPayload) =>
    request<OwnLocation>('/users/me/location', { method: 'PUT', body: payload }),
};

// ---------------------------------------------------------------------------
// Needs
// ---------------------------------------------------------------------------
export type NeedStatus = 'open' | 'partially_fulfilled' | 'fulfilled' | 'closed' | 'expired';
export type ModerationStatus = 'pending' | 'approved' | 'rejected';

export type NeedCard = {
  id: number;
  title: string;
  description: string;
  category_id: number | null;
  category_name: string | null;
  quantity_needed: number;
  status: NeedStatus;
  location: Location;
  created_at: string;
};

export type MyNeed = NeedCard & {
  moderation_status: ModerationStatus;
  moderation_note: string | null;
  expires_at: string | null;
};

export type AdminNeed = MyNeed & { user_id: number; user_label: string };

export type NeedPayload = {
  title: string;
  description?: string;
  category_id?: number | null;
  quantity_needed?: number;
  city?: string | null;
  district?: string | null;
};

/** Aggregated local demand. Counts, never identities. */
export type Demand = {
  key: string;
  label: string;
  count: number;
  category_id: number | null;
  nearest_km: number | null;
};

export type NeedMatch = { need: NeedCard; score: number };

/** A listing request that went to somebody else, offered back as a need. */
export type ConvertibleItem = {
  request_item_id: number;
  title: string;
  product_id: number | null;
  quantity: number;
  decided_at: string | null;
};

export type NeedQuery = {
  q?: string | undefined;
  category_id?: number | undefined;
  city?: string | undefined;
  lat?: number | undefined;
  lng?: number | undefined;
  radius_km?: number | undefined;
  sort?: 'newest' | 'nearby' | undefined;
  page?: number | undefined;
  per_page?: number | undefined;
};

export const needsApi = {
  list: (query: NeedQuery, lang: string, signal?: AbortSignal) =>
    request<Paged<NeedCard>>(`/needs${qs({ ...query, lang })}`, { lang, signal }),

  one: (id: number, lang: string, signal?: AbortSignal) =>
    request<NeedCard>(`/needs/${id}${qs({ lang })}`, { lang, signal }),

  mine: (lang: string, signal?: AbortSignal) =>
    request<MyNeed[]>(`/needs/mine${qs({ lang })}`, { lang, signal }),

  demand: (
    params: { lat?: number; lng?: number; radius_km?: number; limit?: number },
    signal?: AbortSignal,
  ) => request<Demand[]>(`/needs/demand${qs(params)}`, { signal }),

  matchingListings: (id: number, lang: string, signal?: AbortSignal) =>
    request<ProductCard[]>(`/needs/${id}/matching-listings${qs({ lang })}`, { lang, signal }),

  create: (payload: NeedPayload) => request<MyNeed>('/needs', { method: 'POST', body: payload }),

  update: (id: number, payload: Partial<NeedPayload>) =>
    request<MyNeed>(`/needs/${id}`, { method: 'PATCH', body: payload }),

  setStatus: (id: number, status: NeedStatus) =>
    request<MyNeed>(`/needs/${id}/status`, { method: 'POST', body: { status } }),

  /** "Ehtiyac kimi saxla" - the consent step after losing out on a listing. */
  convertible: (signal?: AbortSignal) =>
    request<ConvertibleItem[]>('/needs/convertible', { signal }),

  fromRequestItem: (itemId: number) =>
    request<MyNeed>(`/needs/from-request-item/${itemId}`, { method: 'POST' }),
};

// ---------------------------------------------------------------------------
// Messaging
// ---------------------------------------------------------------------------
export type ConversationType = 'listing' | 'need' | 'loan' | 'emergency';

export type Participant = {
  user_id: number;
  display_name: string;
  avatar_url: string | null;
};

export type Conversation = {
  id: number;
  type: ConversationType;
  context_id: number | null;
  subject: string | null;
  participants: Participant[];
  unread_count: number;
  last_message_at: string | null;
  last_message_preview: string | null;
  created_at: string;
};

export type Message = {
  id: number;
  conversation_id: number;
  sender_id: number;
  body: string;
  created_at: string;
  edited_at: string | null;
  is_deleted: boolean;
};

export type ConversationThread = {
  conversation: Conversation;
  messages: Message[];
  next_before_id: number | null;
};

export type UnreadCounts = { conversations: number; notifications: number };

export const messagesApi = {
  list: (lang: string, signal?: AbortSignal) =>
    request<Conversation[]>(`/conversations${qs({ lang })}`, { lang, signal }),

  unread: (signal?: AbortSignal) => request<UnreadCounts>('/conversations/unread', { signal }),

  thread: (id: number, lang: string, beforeId?: number, signal?: AbortSignal) =>
    request<ConversationThread>(`/conversations/${id}${qs({ lang, before_id: beforeId })}`, {
      lang,
      signal,
    }),

  /** Get-or-create. The server resolves who this reaches from the subject. */
  open: (type: ConversationType, contextId: number) =>
    request<Conversation>('/conversations', {
      method: 'POST',
      body: { type, context_id: contextId },
    }),

  send: (id: number, body: string) =>
    request<Message>(`/conversations/${id}/messages`, { method: 'POST', body: { body } }),

  markRead: (id: number) => request<void>(`/conversations/${id}/read`, { method: 'POST' }),
};

// ---------------------------------------------------------------------------
// Lending
// ---------------------------------------------------------------------------
export type LoanStatus =
  'pending' | 'approved' | 'borrowed' | 'returned' | 'rejected' | 'cancelled';

export type LoanAction = 'approved' | 'rejected' | 'borrowed' | 'returned' | 'cancelled';

export type Loan = {
  id: number;
  product_id: number;
  product_title: string;
  product_slug: string;
  product_image: string | null;
  borrower_id: number;
  borrower_name: string;
  status: LoanStatus;
  role: 'owner' | 'borrower' | null;
  message: string | null;
  owner_note: string | null;
  requested_days: number | null;
  approved_at: string | null;
  borrowed_at: string | null;
  expected_return_at: string | null;
  returned_at: string | null;
  created_at: string;
};

export const loansApi = {
  borrowed: (lang: string, signal?: AbortSignal) =>
    request<Loan[]>(`/loans/mine${qs({ lang })}`, { lang, signal }),

  lent: (lang: string, signal?: AbortSignal) =>
    request<Loan[]>(`/loans/lent${qs({ lang })}`, { lang, signal }),

  one: (id: number, lang: string, signal?: AbortSignal) =>
    request<Loan>(`/loans/${id}${qs({ lang })}`, { lang, signal }),

  requestLoan: (payload: {
    product_id: number;
    requested_days?: number | undefined;
    message?: string | undefined;
  }) => request<Loan>('/loans', { method: 'POST', body: payload }),

  act: (id: number, status: LoanAction, note?: string) =>
    request<Loan>(`/loans/${id}/status`, { method: 'POST', body: { status, note } }),
};

// ---------------------------------------------------------------------------
// Emergency aid
// ---------------------------------------------------------------------------
export type CaseStatus = 'draft' | 'active' | 'paused' | 'completed' | 'cancelled';
export type ItemPriority = 'urgent' | 'normal' | 'low';
export type CommitmentStatus = 'offered' | 'accepted' | 'received' | 'cancelled';

export type AidItem = {
  id: number;
  title: string;
  category_id: number | null;
  quantity_needed: number;
  quantity_committed: number;
  quantity_received: number;
  priority: ItemPriority;
  notes: string | null;
  is_satisfied: boolean;
};

export type AidCase = {
  id: number;
  slug: string;
  title: string;
  beneficiary_display_name: string | null;
  status: CaseStatus;
  location: Location;
  items_total: number;
  items_satisfied: number;
  published_at: string | null;
};

export type AidCaseDetail = AidCase & {
  description: string;
  items: AidItem[];
  accepts_offers: boolean;
};

/**
 * The admin view. `verification_note_internal` exists on no other type in
 * this file, because it exists on no other response from the API.
 */
export type AdminAidCase = AidCaseDetail & {
  verification_note_internal: string | null;
  title_az: string;
  title_en: string | null;
  description_az: string;
  description_en: string | null;
  created_by_admin_id: number;
  closed_at: string | null;
  created_at: string;
};

export type Commitment = {
  id: number;
  item_id: number;
  item_title: string;
  case_id: number;
  case_title: string;
  quantity: number;
  status: CommitmentStatus;
  note: string | null;
  created_at: string;
};

export type AdminCommitment = Commitment & { user_id: number; user_label: string };

export const aidApi = {
  cases: (lang: string, activeOnly = true, signal?: AbortSignal) =>
    request<AidCase[]>(`/aid/cases${qs({ lang, active_only: activeOnly })}`, { lang, signal }),

  one: (key: string, lang: string, signal?: AbortSignal) =>
    request<AidCaseDetail>(`/aid/cases/${encodeURIComponent(key)}${qs({ lang })}`, {
      lang,
      signal,
    }),

  myCommitments: (lang: string, signal?: AbortSignal) =>
    request<Commitment[]>(`/aid/commitments/mine${qs({ lang })}`, { lang, signal }),

  offer: (itemId: number, payload: { quantity: number; note?: string | undefined }) =>
    request<Commitment>(`/aid/items/${itemId}/commitments`, { method: 'POST', body: payload }),

  withdraw: (commitmentId: number) =>
    request<Commitment>(`/aid/commitments/${commitmentId}/status`, {
      method: 'POST',
      body: { status: 'cancelled' },
    }),
};

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------
export type Notification = {
  id: number;
  /** Stable key; the client owns the translated sentence (i18n key
   *  `notification.<type>`), so a stored row is never frozen into one language. */
  type: string;
  payload: Record<string, unknown>;
  link: string | null;
  is_read: boolean;
  created_at: string;
};

export const notificationsApi = {
  list: (signal?: AbortSignal) => request<Notification[]>('/notifications', { signal }),
  markAllRead: () => request<void>('/notifications/read', { method: 'POST' }),
  markRead: (id: number) => request<void>(`/notifications/${id}/read`, { method: 'POST' }),
};

// ---------------------------------------------------------------------------
// Query keys, in one place so invalidation cannot drift from fetching
// ---------------------------------------------------------------------------
export const communityKeys = {
  places: () => ['places'] as const,
  myLocation: () => ['location', 'mine'] as const,

  needs: (query: NeedQuery, lang: string) => ['needs', query, lang] as const,
  need: (id: number, lang: string) => ['need', id, lang] as const,
  myNeeds: (lang: string) => ['needs', 'mine', lang] as const,
  demand: (params: Record<string, unknown>) => ['demand', params] as const,
  needMatches: (id: number, lang: string) => ['need', id, 'matches', lang] as const,
  convertible: () => ['needs', 'convertible'] as const,

  conversations: (lang: string) => ['conversations', lang] as const,
  thread: (id: number, lang: string) => ['conversation', id, lang] as const,
  unread: () => ['unread'] as const,

  borrowed: (lang: string) => ['loans', 'borrowed', lang] as const,
  lent: (lang: string) => ['loans', 'lent', lang] as const,

  aidCases: (lang: string, activeOnly: boolean) => ['aid', 'cases', lang, activeOnly] as const,
  aidCase: (key: string, lang: string) => ['aid', 'case', key, lang] as const,
  myCommitments: (lang: string) => ['aid', 'commitments', lang] as const,

  notifications: () => ['notifications'] as const,
};
