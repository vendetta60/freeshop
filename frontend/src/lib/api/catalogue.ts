import { qs, request } from '@/lib/api/client';
import type { Location, NeedMatch } from '@/lib/api/community';

/**
 * Catalogue API.
 *
 * These types mirror app/schemas/catalogue.py. Once the OpenAPI generation
 * step runs (`npm run gen:api`) they are replaced by generated types; keeping
 * the same names means that swap touches only this file.
 */

export type SortKey =
  'newest' | 'oldest' | 'price_asc' | 'price_desc' | 'relevance' | 'nearby' | 'most_requested';
export type StockStatus = 'available' | 'out_of_stock' | 'on_order';
/**
 * The sorts the discovery surfaces offer, in the order they offer them:
 * where it is, then how new, then how wanted, then price.
 *
 * Data rather than a component, and here rather than in a component file,
 * because more than one page renders it and a module that exports both a
 * component and a constant breaks fast refresh.
 */
export const SORT_OPTIONS: SortKey[] = [
  'nearby',
  'newest',
  'most_requested',
  'price_asc',
  'price_desc',
];

export type TransferType = 'giveaway' | 'loan';
/** Derived server-side from the listing's live loan, never stored. */
export type LoanListingState = 'available' | 'reserved' | 'borrowed';

export type ProductCard = {
  id: number;
  slug: string;
  title: string;
  price_minor: number;
  old_price_minor: number | null;
  currency: string;
  stock_status: StockStatus;
  category_id: number;
  category_name: string;
  image: string | null;
  image_width: number | null;
  image_height: number | null;
  is_featured: boolean;
  location: Location;
  transfer_type: TransferType;
  loan_state: LoanListingState;
};

export type ProductImage = {
  id: number;
  url: string;
  width: number | null;
  height: number | null;
  is_main: boolean;
};

export type ProductDetail = ProductCard & {
  description: string;
  images: ProductImage[];
  created_at: string;
  available_from: string | null;
  available_until: string | null;
  max_borrow_days: number | null;
  /** How many people are waiting on a decision. A count, never names. */
  open_request_count: number;
};

export type CategoryNode = {
  id: number;
  slug: string;
  name: string;
  parent_id: number | null;
  children: CategoryNode[];
  product_count: number;
};

export type Paged<T> = {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
  /** The sort the server actually applied. It differs from the requested one
   *  when `nearby` was asked for with no location to measure from. */
  applied_sort?: string | null;
};

export type Contact = {
  phone: string;
  whatsapp: string;
  telegram: string;
  email: string;
  address: string;
  working_hours: string;
  socials: Record<string, string>;
};

export type ProductQuery = {
  q?: string | undefined;
  category?: string | undefined;
  stock?: StockStatus | undefined;
  sort?: SortKey | undefined;
  featured?: boolean | undefined;
  transfer_type?: TransferType | undefined;
  city?: string | undefined;
  lat?: number | undefined;
  lng?: number | undefined;
  radius_km?: number | undefined;
  page?: number | undefined;
  per_page?: number | undefined;
};

export type ModerationStatus = 'pending' | 'approved' | 'rejected';

/** A listing as its owner sees it, whatever state it is in. */
export type MyListing = {
  id: number;
  slug: string;
  title: string;
  price_minor: number;
  currency: string;
  is_free: boolean;
  category_name: string;
  status: ModerationStatus;
  moderation_note: string | null;
  image: string | null;
  is_deleted: boolean;
  created_at: string;
  reviewed_at: string | null;
  transfer_type: TransferType;
  location_label: string | null;
  /** People still waiting on this owner's decision (FreeShop_Prompt 5). */
  open_request_count: number;
};

/** One person who asked for a listing. Visible ONLY to that listing's owner. */
export type Requester = {
  request_item_id: number;
  request_no: string;
  user_id: number;
  display_name: string;
  note: string | null;
  quantity: number;
  requested_at: string;
};

export type SubmissionPayload = {
  title_az: string;
  title_en?: string | null;
  description_az?: string;
  description_en?: string | null;
  price_minor?: number;
  category_id: number;
  stock_status?: StockStatus;
  city?: string | null;
  district?: string | null;
  transfer_type?: TransferType;
  available_from?: string | null;
  available_until?: string | null;
  max_borrow_days?: number | null;
};

export const listingApi = {
  /** Offer something. Lands in the moderation queue, not on the site. */
  submit: (payload: SubmissionPayload) =>
    request<MyListing>('/products', { method: 'POST', body: payload }),

  /** Photos for a listing you own. Same pipeline as the admin upload. */
  addImages: (productId: number, files: File[]) => {
    const form = new FormData();
    for (const file of files) form.append('files', file);
    return request<ProductImage[]>(`/products/${productId}/images`, {
      method: 'POST',
      body: form,
    });
  },

  mine: (lang: string, signal?: AbortSignal) =>
    request<MyListing[]>(`/products/mine${qs({ lang })}`, { lang, signal }),

  /** Who has asked for one of your listings. Owner-only, server-enforced. */
  requesters: (productId: number, signal?: AbortSignal) =>
    request<Requester[]>(`/products/${productId}/requesters`, { signal }),

  /** Choose a recipient. Returns the people who were not selected, whose
   *  requests become convertible demand rather than disappearing (Rule C). */
  handover: (productId: number, requestItemId: number) =>
    request<Requester[]>(`/products/${productId}/handover`, {
      method: 'POST',
      body: { request_item_id: requestItemId },
    }),

  /** Open needs this listing could answer (FreeShop_Prompt 6). */
  matchingNeeds: (productId: number, lang: string, signal?: AbortSignal) =>
    request<NeedMatch[]>(`/products/${productId}/matching-needs${qs({ lang })}`, {
      lang,
      signal,
    }),
};

export const listingKeys = {
  mine: (lang: string) => ['listings', 'mine', lang] as const,
  requesters: (productId: number) => ['listings', productId, 'requesters'] as const,
  matchingNeeds: (productId: number, lang: string) =>
    ['listings', productId, 'matching-needs', lang] as const,
};

export const catalogueApi = {
  categories: (lang: string, signal?: AbortSignal) =>
    request<CategoryNode[]>(`/categories${qs({ lang })}`, { lang, signal }),

  products: (query: ProductQuery, lang: string, signal?: AbortSignal) =>
    request<Paged<ProductCard>>(`/products${qs({ ...query, lang })}`, { lang, signal }),

  product: (slug: string, lang: string, signal?: AbortSignal) =>
    request<ProductDetail>(`/products/${encodeURIComponent(slug)}${qs({ lang })}`, {
      lang,
      signal,
    }),

  related: (slug: string, lang: string, signal?: AbortSignal) =>
    request<ProductCard[]>(`/products/${encodeURIComponent(slug)}/related${qs({ lang })}`, {
      lang,
      signal,
    }),

  contact: (lang: string, signal?: AbortSignal) =>
    request<Contact>(`/meta/contact${qs({ lang })}`, { lang, signal }),
};

/** Query keys in one place, so invalidation cannot drift from fetching. */
export const catalogueKeys = {
  categories: (lang: string) => ['categories', lang] as const,
  products: (query: ProductQuery, lang: string) => ['products', query, lang] as const,
  product: (slug: string, lang: string) => ['product', slug, lang] as const,
  related: (slug: string, lang: string) => ['related', slug, lang] as const,
  contact: (lang: string) => ['contact', lang] as const,
};
