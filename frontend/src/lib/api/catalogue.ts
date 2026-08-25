import { qs, request } from '@/lib/api/client';

/**
 * Catalogue API.
 *
 * These types mirror app/schemas/catalogue.py. Once the OpenAPI generation
 * step runs (`npm run gen:api`) they are replaced by generated types; keeping
 * the same names means that swap touches only this file.
 */

export type SortKey = 'newest' | 'oldest' | 'price_asc' | 'price_desc' | 'relevance';
export type StockStatus = 'available' | 'out_of_stock' | 'on_order';

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
};

export type SubmissionPayload = {
  title_az: string;
  title_en?: string | null;
  description_az?: string;
  description_en?: string | null;
  price_minor?: number;
  category_id: number;
  stock_status?: StockStatus;
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
};

export const listingKeys = {
  mine: (lang: string) => ['listings', 'mine', lang] as const,
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
