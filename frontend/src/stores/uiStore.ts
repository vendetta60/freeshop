import { create } from 'zustand';

import type { ProductCard as ProductSummary } from '@/lib/api/catalogue';

type UiState = {
  cartOpen: boolean;
  paletteOpen: boolean;
  categoryMenuOpen: boolean;
  accountMenuOpen: boolean;
  authOpen: boolean;

  /**
   * The "add to cart" a guest attempted (plan.md 9.8).
   *
   * Held in memory while the sign-in sheet is open and replayed the moment
   * they sign in, so their action completes and they never re-click. Exactly
   * one item, cleared on use or dismiss - an interrupted action, not a cart.
   */
  pendingIntent: ProductSummary | null;

  openCart: () => void;
  closeCart: () => void;
  setPaletteOpen: (open: boolean) => void;
  toggleCategoryMenu: () => void;
  closeCategoryMenu: () => void;
  toggleAccountMenu: () => void;
  closeAccountMenu: () => void;
  openAuth: () => void;
  closeAuth: () => void;
  /** Guest pressed "Səbətə at": remember it and invite them to sign in. */
  requestSignIn: (product: ProductSummary) => void;
  clearIntent: () => void;
};

export const useUiStore = create<UiState>()((set) => ({
  cartOpen: false,
  paletteOpen: false,
  categoryMenuOpen: false,
  accountMenuOpen: false,
  authOpen: false,
  pendingIntent: null,

  openCart: () => set({ cartOpen: true, categoryMenuOpen: false, accountMenuOpen: false }),
  closeCart: () => set({ cartOpen: false }),

  setPaletteOpen: (open) =>
    set({ paletteOpen: open, categoryMenuOpen: false, accountMenuOpen: false }),

  toggleCategoryMenu: () =>
    set((s) => ({ categoryMenuOpen: !s.categoryMenuOpen, accountMenuOpen: false })),
  closeCategoryMenu: () => set({ categoryMenuOpen: false }),

  toggleAccountMenu: () =>
    set((s) => ({ accountMenuOpen: !s.accountMenuOpen, categoryMenuOpen: false })),
  closeAccountMenu: () => set({ accountMenuOpen: false }),

  openAuth: () => set({ authOpen: true, accountMenuOpen: false, cartOpen: false }),
  // Dismissing abandons the intent: it is a single interrupted action, not
  // something that should linger and surprise the visitor later.
  closeAuth: () => set({ authOpen: false, pendingIntent: null }),

  requestSignIn: (product) => set({ pendingIntent: product, authOpen: true, cartOpen: false }),
  clearIntent: () => set({ pendingIntent: null }),
}));
