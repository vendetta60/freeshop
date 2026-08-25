import type { ProductCard } from '@/lib/api/catalogue';
import { request } from '@/lib/api/client';

export type CartLine = {
  id: number;
  quantity: number;
  line_total_minor: number;
  product: ProductCard;
};

export type Cart = {
  lines: CartLine[];
  total_minor: number;
  item_count: number;
  currency: string;
};

export type OrderRequestItem = {
  id: number;
  title: string;
  quantity: number;
  price_minor: number;
  line_total_minor: number;
  product_slug: string | null;
  image: string | null;
};

export type OrderRequest = {
  id: number;
  request_no: string;
  status: 'new' | 'viewed' | 'completed' | 'cancelled';
  contact_phone: string;
  contact_email: string | null;
  note: string | null;
  total_minor: number;
  created_at: string;
  items: OrderRequestItem[];
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

export type OrderRequestCreated = {
  request: OrderRequest;
  contact: Contact;
};

export const cartApi = {
  get: (signal?: AbortSignal) => request<Cart>('/cart', { signal }),

  add: (productId: number, quantity = 1) =>
    request<Cart>('/cart/items', {
      method: 'POST',
      body: { product_id: productId, quantity },
    }),

  setQuantity: (lineId: number, quantity: number) =>
    request<Cart>(`/cart/items/${lineId}`, { method: 'PATCH', body: { quantity } }),

  remove: (lineId: number) => request<Cart>(`/cart/items/${lineId}`, { method: 'DELETE' }),

  clear: () => request<void>('/cart', { method: 'DELETE' }),
};

export const orderApi = {
  submit: (
    payload: { contact_phone: string; contact_email?: string; note?: string },
    idempotencyKey: string,
  ) =>
    request<OrderRequestCreated>('/order-requests', {
      method: 'POST',
      body: payload,
      // Turns a double-tapped submit button into one request, not two.
      headers: { 'Idempotency-Key': idempotencyKey },
    }),

  mine: (signal?: AbortSignal) => request<OrderRequest[]>('/order-requests/me', { signal }),

  /** One of your own requests. Filtered by the user id in the token, never by
   *  the id in the URL (plan.md 10, IDOR) - so a guessed id is a 404. */
  byId: (id: number, signal?: AbortSignal) =>
    request<OrderRequest>(`/order-requests/me/${id}`, { signal }),
};

export const cartKeys = {
  cart: () => ['cart'] as const,
  myRequests: () => ['order-requests', 'me'] as const,
  myRequest: (id: number) => ['order-requests', 'me', id] as const,
};
