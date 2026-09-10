import type { OrderRequest } from '@/lib/api/cart';
import type { Paged, ProductImage, StockStatus } from '@/lib/api/catalogue';
import { qs, request } from '@/lib/api/client';

/**
 * Admin API.
 *
 * Mirrors app/schemas/admin.py, which deliberately returns the RAW bilingual
 * fields rather than the resolved ones the public API serves: the panel edits
 * the record, and a form that saved the AZ fallback into the EN column would
 * quietly erase the difference between "not translated" and "translated the
 * same" (plan.md 7.3).
 */

export type AdminProduct = {
  id: number;
  slug: string;
  title_az: string;
  title_en: string | null;
  description_az: string;
  description_en: string | null;
  price_minor: number;
  old_price_minor: number | null;
  currency: string;
  category_id: number;
  category_name: string;
  stock_status: StockStatus;
  is_featured: boolean;
  is_deleted: boolean;
  is_free: boolean;
  has_en: boolean;
  status: ModerationStatus;
  moderation_note: string | null;
  owner_id: number;
  owner_name: string | null;
  owner_phone: string | null;
  reviewed_at: string | null;
  images: ProductImage[];
  created_at: string;
  updated_at: string;
};

export type AdminCategory = {
  id: number;
  slug: string;
  name_az: string;
  name_en: string | null;
  parent_id: number | null;
  icon: string | null;
  sort_order: number;
  is_active: boolean;
  product_count: number;
};

export type AdminUser = {
  id: number;
  email: string | null;
  phone: string | null;
  phone_verified: boolean;
  full_name: string | null;
  role: string;
  is_active: boolean;
  preferred_lang: string;
  last_login_at: string | null;
  created_at: string;
  request_count: number;
};

export type AdminOrderRequest = OrderRequest & {
  admin_note: string | null;
  user_id: number;
  user_name: string | null;
  user_email: string | null;
  user_phone: string | null;
};

export type RequestStatus = 'new' | 'viewed' | 'completed' | 'cancelled';

export type ModerationStatus = 'pending' | 'approved' | 'rejected';

export type Stats = {
  products: number;
  products_pending: number;
  products_deleted: number;
  categories: number;
  users: number;
  requests_total: number;
  requests_new: number;
  requests_completed: number;
  revenue_requested_minor: number;
  series: { date: string; count: number }[];
};

export type ProductPayload = {
  title_az: string;
  title_en?: string | null;
  description_az?: string;
  description_en?: string | null;
  price_minor: number;
  old_price_minor?: number | null;
  currency?: string;
  category_id: number;
  stock_status?: StockStatus;
  is_featured?: boolean;
  slug?: string | null;
};

export type CategoryPayload = {
  name_az: string;
  name_en?: string | null;
  parent_id?: number | null;
  icon?: string | null;
  sort_order?: number;
  is_active?: boolean;
};

export type SiteSettings = Record<string, unknown>;

export type ProductListQuery = {
  q?: string | undefined;
  category_id?: number | undefined;
  stock?: StockStatus | undefined;
  status?: ModerationStatus | undefined;
  include_deleted?: boolean | undefined;
  page?: number | undefined;
  per_page?: number | undefined;
};

export const adminApi = {
  // --- products ---
  products: (query: ProductListQuery, signal?: AbortSignal) =>
    request<Paged<AdminProduct>>(`/admin/products${qs({ ...query })}`, { signal }),

  product: (id: number, signal?: AbortSignal) =>
    request<AdminProduct>(`/admin/products/${id}`, { signal }),

  createProduct: (payload: ProductPayload) =>
    request<AdminProduct>('/admin/products', { method: 'POST', body: payload }),

  updateProduct: (id: number, payload: Partial<ProductPayload>) =>
    request<AdminProduct>(`/admin/products/${id}`, { method: 'PATCH', body: payload }),

  deleteProduct: (id: number) => request<void>(`/admin/products/${id}`, { method: 'DELETE' }),

  restoreProduct: (id: number) =>
    request<AdminProduct>(`/admin/products/${id}/restore`, { method: 'POST' }),

  /** The decision that puts an offer on the site, or does not. */
  moderate: (id: number, body: { status: 'approved' | 'rejected'; note?: string }) =>
    request<AdminProduct>(`/admin/products/${id}/moderate`, { method: 'POST', body }),

  // --- images ---
  uploadImages: (productId: number, files: File[]) => {
    const form = new FormData();
    for (const file of files) form.append('files', file);
    return request<ProductImage[]>(`/admin/products/${productId}/images`, {
      method: 'POST',
      body: form,
    });
  },

  updateImage: (
    productId: number,
    imageId: number,
    patch: { is_main?: boolean; sort_order?: number },
  ) =>
    request<AdminProduct>(`/admin/products/${productId}/images/${imageId}`, {
      method: 'PATCH',
      body: patch,
    }),

  deleteImage: (productId: number, imageId: number) =>
    request<void>(`/admin/products/${productId}/images/${imageId}`, { method: 'DELETE' }),

  // --- categories ---
  categories: (signal?: AbortSignal) => request<AdminCategory[]>('/admin/categories', { signal }),

  createCategory: (payload: CategoryPayload) =>
    request<AdminCategory>('/admin/categories', { method: 'POST', body: payload }),

  updateCategory: (id: number, payload: Partial<CategoryPayload>) =>
    request<AdminCategory>(`/admin/categories/${id}`, { method: 'PATCH', body: payload }),

  deleteCategory: (id: number) => request<void>(`/admin/categories/${id}`, { method: 'DELETE' }),

  // --- order requests ---
  requests: (
    query: { status?: string | undefined; q?: string | undefined; page?: number | undefined },
    signal?: AbortSignal,
  ) => request<Paged<AdminOrderRequest>>(`/admin/order-requests${qs({ ...query })}`, { signal }),

  updateRequest: (id: number, patch: { status?: RequestStatus; admin_note?: string }) =>
    request<AdminOrderRequest>(`/admin/order-requests/${id}`, { method: 'PATCH', body: patch }),

  // --- users ---
  users: (query: { q?: string | undefined; page?: number | undefined }, signal?: AbortSignal) =>
    request<Paged<AdminUser>>(`/admin/users${qs({ ...query })}`, { signal }),

  // --- settings ---
  settings: (signal?: AbortSignal) => request<SiteSettings>('/admin/settings', { signal }),

  saveSettings: (values: SiteSettings) =>
    request<SiteSettings>('/admin/settings', { method: 'PATCH', body: { values } }),

  // --- dashboard ---
  stats: (signal?: AbortSignal) => request<Stats>('/admin/stats', { signal }),

  recentRequests: (signal?: AbortSignal) =>
    request<
      {
        id: number;
        request_no: string;
        status: RequestStatus;
        total_minor: number;
        created_at: string;
      }[]
    >('/admin/stats/recent-requests', { signal }),
};

export const adminKeys = {
  products: (query: ProductListQuery) => ['admin', 'products', query] as const,
  product: (id: number) => ['admin', 'product', id] as const,
  categories: () => ['admin', 'categories'] as const,
  requests: (query: Record<string, unknown>) => ['admin', 'requests', query] as const,
  users: (query: Record<string, unknown>) => ['admin', 'users', query] as const,
  settings: () => ['admin', 'settings'] as const,
  stats: () => ['admin', 'stats'] as const,
  recent: () => ['admin', 'recent-requests'] as const,
};

// ---------------------------------------------------------------------------
// Needs moderation and emergency aid (FreeShop_Prompt 11)
//
// Appended rather than split into a second admin module: the panel is one
// surface, `adminKeys` is one namespace, and a second file would only make
// invalidation span two of them.
// ---------------------------------------------------------------------------
import type {
  AdminAidCase,
  AdminCommitment,
  AdminNeed,
  AidItem,
  CaseStatus,
  CommitmentStatus,
  ItemPriority,
} from '@/lib/api/community';

export type AidCasePayload = {
  title_az: string;
  title_en?: string | null;
  description_az?: string;
  description_en?: string | null;
  beneficiary_display_name?: string | null;
  /** Admin-only, and the only field in the app with that property. */
  verification_note_internal?: string | null;
  city?: string | null;
  district?: string | null;
};

export type AidItemPayload = {
  title_az: string;
  title_en?: string | null;
  category_id?: number | null;
  quantity_needed?: number;
  priority?: ItemPriority;
  notes?: string | null;
};

export const adminCommunityApi = {
  needs: (params: { status?: string; page?: number; per_page?: number }, signal?: AbortSignal) =>
    request<Paged<AdminNeed>>(`/admin/needs${qs(params)}`, { signal }),

  moderateNeed: (id: number, body: { status: 'approved' | 'rejected'; note?: string }) =>
    request<AdminNeed>(`/admin/needs/${id}/moderate`, { method: 'POST', body }),

  aidCases: (signal?: AbortSignal) => request<AdminAidCase[]>('/admin/aid/cases', { signal }),

  aidCase: (id: number, signal?: AbortSignal) =>
    request<AdminAidCase>(`/admin/aid/cases/${id}`, { signal }),

  createCase: (body: AidCasePayload) =>
    request<AdminAidCase>('/admin/aid/cases', { method: 'POST', body }),

  updateCase: (id: number, body: Partial<AidCasePayload>) =>
    request<AdminAidCase>(`/admin/aid/cases/${id}`, { method: 'PATCH', body }),

  setCaseStatus: (id: number, status: CaseStatus) =>
    request<AdminAidCase>(`/admin/aid/cases/${id}/status`, { method: 'POST', body: { status } }),

  addItem: (caseId: number, body: AidItemPayload) =>
    request<AidItem>(`/admin/aid/cases/${caseId}/items`, { method: 'POST', body }),

  updateItem: (itemId: number, body: Partial<AidItemPayload>) =>
    request<AidItem>(`/admin/aid/items/${itemId}`, { method: 'PATCH', body }),

  deleteItem: (itemId: number) => request<void>(`/admin/aid/items/${itemId}`, { method: 'DELETE' }),

  commitments: (caseId: number, signal?: AbortSignal) =>
    request<AdminCommitment[]>(`/admin/aid/cases/${caseId}/commitments`, { signal }),

  setCommitmentStatus: (commitmentId: number, status: CommitmentStatus) =>
    request<AdminCommitment>(`/admin/aid/commitments/${commitmentId}/status`, {
      method: 'POST',
      body: { status },
    }),
};

export const adminCommunityKeys = {
  needs: (params: Record<string, unknown>) => ['admin', 'needs', params] as const,
  aidCases: () => ['admin', 'aid', 'cases'] as const,
  aidCase: (id: number) => ['admin', 'aid', 'case', id] as const,
  commitments: (caseId: number) => ['admin', 'aid', 'commitments', caseId] as const,
};
