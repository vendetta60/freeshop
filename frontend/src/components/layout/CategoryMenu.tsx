import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';

import { useCategories } from '@/lib/hooks/useCategories';
import { useT } from '@/lib/i18n';
import { useUiStore } from '@/stores/uiStore';

/**
 * Category dropdown.
 *
 * Click-triggered, never hover: hover menus are hostile on touch-capable
 * laptops (plan.md 3.6). Closes on Escape, outside click, or selection.
 */
export function CategoryMenu() {
  const { t } = useT();
  const open = useUiStore((s) => s.categoryMenuOpen);
  const close = useUiStore((s) => s.closeCategoryMenu);
  const navigate = useNavigate();
  const { flat: categories } = useCategories();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    const onClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) close();
    };
    document.addEventListener('keydown', onKey);
    // Deferred so the click that opened the menu does not immediately close it.
    const id = setTimeout(() => document.addEventListener('click', onClick), 0);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onClick);
      clearTimeout(id);
    };
  }, [open, close]);

  if (!open) return null;

  const go = (to: string) => {
    close();
    void navigate(to);
  };

  return (
    <div ref={ref} className="glass glass--specular glass--deep category-menu" role="menu">
      <button
        type="button"
        role="menuitem"
        className="category-menu__item"
        onClick={() => {
          go('/products');
        }}
      >
        {t('common.all')}
      </button>
      {categories.map((category) => (
        <button
          key={category.slug}
          type="button"
          role="menuitem"
          className="category-menu__item"
          onClick={() => {
            go(`/products?category=${encodeURIComponent(category.slug)}`);
          }}
        >
          <span>{category.name}</span>
          <span className="category-menu__count">{category.product_count}</span>
        </button>
      ))}
    </div>
  );
}
