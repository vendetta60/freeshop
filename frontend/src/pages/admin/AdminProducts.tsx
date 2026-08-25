import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Plus, RotateCcw, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Pagination } from '@/components/ui/Pagination';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { adminApi, adminKeys, type AdminProduct } from '@/lib/api/admin';
import { useT } from '@/lib/i18n';
import { ApiError } from '@/lib/api/client';
import { useDebounced } from '@/lib/hooks/useDebounced';
import { Price } from '@/components/ui/Price';
import { toast } from '@/stores/toastStore';

/**
 * The product table.
 *
 * Deleted rows are reachable behind a toggle rather than hidden for good: a
 * soft delete the panel cannot show is indistinguishable from a hard one,
 * which would make the mechanism pointless (plan.md 9.6).
 */
export default function AdminProducts() {
  const { t } = useT();
  const [search, setSearch] = useState('');
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [page, setPage] = useState(1);
  const q = useDebounced(search, 250);

  const queryClient = useQueryClient();
  const query = { q: q || undefined, include_deleted: includeDeleted || undefined, page };

  const products = useQuery({
    queryKey: adminKeys.products(query),
    queryFn: ({ signal }) => adminApi.products(query, signal),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin'] });

  const remove = useMutation({
    mutationFn: (product: AdminProduct) => adminApi.deleteProduct(product.id),
    onSuccess: async (_data, product) => {
      toast.success(t('admin.product.removed', { title: product.title_az }));
      await invalidate();
    },
    onError: () => toast.error(t('admin.product.deleteFailed')),
  });

  const restore = useMutation({
    mutationFn: (product: AdminProduct) => adminApi.restoreProduct(product.id),
    onSuccess: async () => {
      toast.success(t('admin.product.restored'));
      await invalidate();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : t('admin.product.restoreFailed')),
  });

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.products')}</h1>
        <Link to="/admin/products/new" className="btn btn--primary btn--sm">
          <Plus size={15} aria-hidden="true" />
          {t('admin.product.new')}
        </Link>
      </header>

      <div className="admin__toolbar">
        <input
          className="input"
          type="search"
          value={search}
          placeholder={t('admin.product.searchPlaceholder')}
          aria-label={t('admin.product.searchLabel')}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
        <label className="field field--inline" style={{ whiteSpace: 'nowrap' }}>
          <input
            type="checkbox"
            className="checkbox"
            checked={includeDeleted}
            onChange={(e) => {
              setIncludeDeleted(e.target.checked);
              setPage(1);
            }}
          />
          <span className="field__label field__label--inline">
            {t('admin.product.showDeleted')}
          </span>
        </label>
      </div>

      {products.isError && <ErrorState onRetry={() => void products.refetch()} />}

      {products.isPending && (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} height={56} radius="var(--r-md)" />
          ))}
        </div>
      )}

      {products.data && products.data.items.length === 0 && (
        <EmptyState
          title={q ? t('admin.product.emptyQuery') : t('admin.product.empty')}
          description={q ? t('admin.product.emptyQueryText') : t('admin.product.emptyText')}
          action={
            !q && (
              <Link to="/admin/products/new" className="btn btn--primary btn--sm">
                {t('admin.product.new')}
              </Link>
            )
          }
        />
      )}

      {products.data && products.data.items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t('admin.product.column')}</th>
                <th scope="col">{t('admin.product.category')}</th>
                <th scope="col">{t('admin.product.price')}</th>
                <th scope="col">{t('admin.product.stock')}</th>
                <th scope="col">
                  <span className="sr-only">{t('common.actions')}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {products.data.items.map((product) => (
                <tr key={product.id} className={product.is_deleted ? 'row--muted' : undefined}>
                  <td>
                    <div className="cell-title">
                      {product.images[0] ? (
                        <img
                          src={product.images[0].url}
                          alt=""
                          width={40}
                          height={40}
                          loading="lazy"
                        />
                      ) : (
                        <span className="cell-title__blank" aria-hidden="true" />
                      )}
                      <span style={{ minWidth: 0 }}>
                        <span className="cell-title__text">{product.title_az}</span>
                        <span className="cell-title__meta">
                          {/* Translation coverage at a glance (plan.md 7.3). */}
                          {product.has_en && <Badge tone="neutral">EN</Badge>}
                          {product.is_featured && (
                            <Badge tone="accent">{t('admin.product.featured')}</Badge>
                          )}
                          {product.is_deleted && (
                            <Badge tone="danger">{t('admin.product.deleted')}</Badge>
                          )}
                        </span>
                      </span>
                    </div>
                  </td>
                  <td className="muted">{product.category_name}</td>
                  <td>
                    <Price minor={product.price_minor} currency={product.currency} />
                  </td>
                  <td className="muted">{t(`stock.${product.stock_status}`)}</td>
                  <td>
                    <div className="row-actions">
                      <Link
                        to={`/admin/products/${product.id}`}
                        className="btn btn--ghost btn--sm btn--icon"
                        aria-label={t('admin.product.editLabel', { title: product.title_az })}
                      >
                        <Pencil size={15} aria-hidden="true" />
                      </Link>
                      {product.is_deleted ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          icon
                          aria-label={t('admin.product.restoreLabel', { title: product.title_az })}
                          disabled={restore.isPending}
                          onClick={() => restore.mutate(product)}
                        >
                          <RotateCcw size={15} aria-hidden="true" />
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          icon
                          aria-label={t('admin.product.deleteLabel', { title: product.title_az })}
                          disabled={remove.isPending}
                          onClick={() => {
                            // Reversible, but still destructive enough that a
                            // mis-click should not silently take a listing off
                            // the site.
                            if (
                              confirm(t('admin.product.confirmDelete', { title: product.title_az }))
                            ) {
                              remove.mutate(product);
                            }
                          }}
                        >
                          <Trash2 size={15} aria-hidden="true" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {products.data && (
        <Pagination
          page={products.data.page}
          pages={products.data.pages}
          total={products.data.total}
          onChange={setPage}
        />
      )}
    </section>
  );
}
