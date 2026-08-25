import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { type Cart, cartApi, cartKeys } from '@/lib/api/cart';
import { useAuthStore } from '@/stores/authStore';

const EMPTY: Cart = { lines: [], total_minor: 0, item_count: 0, currency: 'AZN' };

/**
 * The cart, served by the API.
 *
 * Server-owned rather than client-owned, so it follows the user between
 * devices (plan.md 4.3). Only fetched when signed in - a guest has no cart
 * by design (plan.md D2), and requesting one would just 401 on every render.
 *
 * Every mutation returns the whole cart, so the badge, totals and drawer all
 * update from one response instead of needing a refetch.
 */
export function useCart() {
  const signedIn = useAuthStore((s) => s.user !== null);
  const client = useQueryClient();

  const query = useQuery({
    queryKey: cartKeys.cart(),
    queryFn: ({ signal }) => cartApi.get(signal),
    enabled: signedIn,
    staleTime: 10_000,
  });

  const write = (cart: Cart) => {
    client.setQueryData(cartKeys.cart(), cart);
  };

  const add = useMutation({
    mutationFn: ({ productId, quantity }: { productId: number; quantity?: number }) =>
      cartApi.add(productId, quantity ?? 1),
    onSuccess: write,
  });

  const setQuantity = useMutation({
    mutationFn: ({ lineId, quantity }: { lineId: number; quantity: number }) =>
      cartApi.setQuantity(lineId, quantity),
    onSuccess: write,
  });

  const remove = useMutation({
    mutationFn: (lineId: number) => cartApi.remove(lineId),
    onSuccess: write,
  });

  const cart = signedIn ? (query.data ?? EMPTY) : EMPTY;

  return {
    cart,
    isPending: signedIn && query.isPending,
    add,
    setQuantity,
    remove,
    invalidate: () => client.invalidateQueries({ queryKey: cartKeys.cart() }),
  };
}

export function useCartCount(): number {
  const { cart } = useCart();
  return cart.item_count;
}
