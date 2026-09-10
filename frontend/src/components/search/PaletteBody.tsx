import { useQuery } from '@tanstack/react-query';
import { Command } from 'cmdk';
import { useState } from 'react';
import { useNavigate } from 'react-router';

import { Price } from '@/components/ui/Price';
import { catalogueApi, catalogueKeys } from '@/lib/api/catalogue';
import { useCategories } from '@/lib/hooks/useCategories';
import { useDebounced } from '@/lib/hooks/useDebounced';
import { useT } from '@/lib/i18n';

/**
 * The palette itself - the half that costs something.
 *
 * SPLIT OUT AND LAZY-LOADED (see SearchPalette.tsx) because `cmdk` is a
 * dependency the first paint does not need: the palette is a modal that
 * renders nothing until somebody presses Ctrl+K or taps search. Keeping it
 * in the entry chunk spent part of the plan.md 11 budget on a component
 * most visits never open.
 *
 * The trade is one small fetch on the FIRST open, which is a keystroke the
 * user has already committed to - and the chunk is cached from then on.
 */
export default function PaletteBody({ onClose }: { onClose: () => void }) {
  const [value, setValue] = useState('');
  const navigate = useNavigate();

  // 250ms so a fast typist issues one request, not one per keystroke.
  const debounced = useDebounced(value, 250);
  const { t, lang } = useT();
  const { flat: categories } = useCategories();

  const query = { q: debounced || undefined, per_page: 6, sort: 'relevance' as const };
  const { data } = useQuery({
    queryKey: catalogueKeys.products(query, lang),
    queryFn: ({ signal }) => catalogueApi.products(query, lang, signal),
  });

  const products = data?.items ?? [];
  const matchedCategories = categories.filter((category) =>
    category.name.toLocaleLowerCase('az').includes(debounced.toLocaleLowerCase('az')),
  );

  const go = (to: string) => {
    onClose();
    void navigate(to);
  };

  return (
    <>
      <button type="button" className="scrim" aria-label={t('common.close')} onClick={onClose} />
      <Command
        label={t('nav.searchTab')}
        className="glass glass--specular glass--deep palette"
        shouldFilter={false}
        loop
      >
        <Command.Input
          // Focusing the field is the entire point of a command palette; the
          // generic a11y warning does not apply to a modal search surface.
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus
          value={value}
          onValueChange={setValue}
          placeholder={t('search.placeholder')}
          className="palette__input"
        />
        <Command.List className="palette__list">
          <Command.Empty className="palette__empty">{t('search.empty')}</Command.Empty>

          {products.length > 0 && (
            <Command.Group heading={t('search.products')} className="palette__group">
              {products.map((product) => (
                <Command.Item
                  key={product.id}
                  value={product.slug}
                  onSelect={() => {
                    go(`/products/${product.slug}`);
                  }}
                  className="palette__item"
                >
                  <span className="palette__thumb">
                    {product.image ? <img src={product.image} alt="" loading="lazy" /> : null}
                  </span>
                  <span style={{ minWidth: 0, flex: 1 }}>{product.title}</span>
                  <Price minor={product.price_minor} className="subtle" />
                </Command.Item>
              ))}
            </Command.Group>
          )}

          {matchedCategories.length > 0 && (
            <Command.Group heading="Kateqoriyalar" className="palette__group">
              {matchedCategories.map((category) => (
                <Command.Item
                  key={category.slug}
                  value={`cat-${category.slug}`}
                  onSelect={() => {
                    go(`/products?category=${encodeURIComponent(category.slug)}`);
                  }}
                  className="palette__item"
                >
                  {category.name}
                </Command.Item>
              ))}
            </Command.Group>
          )}
        </Command.List>
      </Command>
    </>
  );
}
