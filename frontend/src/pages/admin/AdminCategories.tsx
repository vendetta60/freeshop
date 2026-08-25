import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { CheckboxField, SelectField, TextField } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { adminApi, adminKeys, type AdminCategory, type CategoryPayload } from '@/lib/api/admin';
import { ApiError, reasonOf } from '@/lib/api/client';
import { useT } from '@/lib/i18n';
import { toast } from '@/stores/toastStore';

type Draft = {
  name_az: string;
  name_en: string;
  parent_id: string;
  sort_order: string;
  is_active: boolean;
};

const EMPTY: Draft = { name_az: '', name_en: '', parent_id: '', sort_order: '0', is_active: true };

function toPayload(draft: Draft): CategoryPayload {
  return {
    name_az: draft.name_az.trim(),
    name_en: draft.name_en.trim() || null,
    parent_id: draft.parent_id ? Number(draft.parent_id) : null,
    sort_order: Number(draft.sort_order) || 0,
    is_active: draft.is_active,
  };
}

/**
 * Category manager.
 *
 * One flat table with an indent rather than a nested tree widget: the model
 * is exactly two levels deep (plan.md D11), so a generic tree control would
 * be a lot of machinery for a shape that cannot vary.
 */
export default function AdminCategories() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<Draft>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const categories = useQuery({
    queryKey: adminKeys.categories(),
    queryFn: ({ signal }) => adminApi.categories(signal),
  });

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['admin'] });
    await queryClient.invalidateQueries({ queryKey: ['categories'] });
  };

  const messageFor = (err: unknown): string => {
    if (!(err instanceof ApiError)) return t('error.generic');
    if (err.code === 'CATEGORY_NOT_EMPTY') {
      const products = Number(err.details.products ?? 0);
      const children = Number(err.details.children ?? 0);
      // Say what is in the way; "cannot delete" alone leaves the admin
      // guessing which of the two rules they hit.
      return children
        ? t('admin.category.hasChildren', { count: children })
        : t('admin.category.hasProducts', { count: products });
    }
    if (reasonOf(err) === 'max_depth_2') return t('admin.category.maxDepth');
    if (reasonOf(err) === 'has_children') return t('admin.category.cannotReparent');
    return err.message;
  };

  const create = useMutation({
    mutationFn: () => adminApi.createCategory(toPayload(draft)),
    onSuccess: async () => {
      setDraft(EMPTY);
      setError(null);
      await invalidate();
      toast.success(t('admin.category.created'));
    },
    onError: (err) => setError(messageFor(err)),
  });

  const update = useMutation({
    mutationFn: (id: number) => adminApi.updateCategory(id, toPayload(editDraft)),
    onSuccess: async () => {
      setEditing(null);
      await invalidate();
      toast.success(t('admin.category.updated'));
    },
    onError: (err) => toast.error(messageFor(err)),
  });

  const remove = useMutation({
    mutationFn: (category: AdminCategory) => adminApi.deleteCategory(category.id),
    onSuccess: async () => {
      await invalidate();
      toast.success(t('admin.category.deleted'));
    },
    onError: (err) => toast.error(messageFor(err)),
  });

  const roots = (categories.data ?? []).filter((c) => c.parent_id === null);
  const ordered = roots.flatMap((root) => [
    root,
    ...(categories.data ?? []).filter((c) => c.parent_id === root.id),
  ]);

  const startEdit = (category: AdminCategory) => {
    setEditing(category.id);
    setEditDraft({
      name_az: category.name_az,
      name_en: category.name_en ?? '',
      parent_id: category.parent_id ? String(category.parent_id) : '',
      sort_order: String(category.sort_order),
      is_active: category.is_active,
    });
  };

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.categories')}</h1>
      </header>

      <form
        className="card admin__form"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.name_az.trim().length < 2) {
            setError(t('admin.validation.title'));
            return;
          }
          create.mutate();
        }}
      >
        <h2 style={{ fontSize: '1rem' }}>{t('admin.category.new')}</h2>
        <div className="form-row">
          <TextField
            label={t('admin.category.nameAz')}
            required
            value={draft.name_az}
            error={error}
            onChange={(e) => {
              setDraft({ ...draft, name_az: e.target.value });
              setError(null);
            }}
          />
          <TextField
            label={t('admin.category.nameEn')}
            value={draft.name_en}
            hint={t('common.optional')}
            onChange={(e) => setDraft({ ...draft, name_en: e.target.value })}
          />
        </div>
        <div className="form-row">
          <SelectField
            label={t('admin.category.parent')}
            value={draft.parent_id}
            onChange={(e) => setDraft({ ...draft, parent_id: e.target.value })}
          >
            <option value="">{t('admin.category.noParent')}</option>
            {roots.map((root) => (
              <option key={root.id} value={root.id}>
                {root.name_az}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t('admin.category.sort')}
            inputMode="numeric"
            value={draft.sort_order}
            onChange={(e) => setDraft({ ...draft, sort_order: e.target.value })}
          />
        </div>
        <Button variant="primary" size="sm" type="submit" disabled={create.isPending}>
          <Plus size={15} aria-hidden="true" />
          {t('admin.category.add')}
        </Button>
      </form>

      {categories.isError && <ErrorState onRetry={() => void categories.refetch()} />}
      {categories.isPending && <Skeleton height={200} radius="var(--r-lg)" />}

      {categories.data && categories.data.length === 0 && (
        <EmptyState title={t('admin.category.empty')} description={t('admin.category.emptyText')} />
      )}

      {ordered.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t('admin.category.name')}</th>
                <th scope="col">{t('admin.category.slug')}</th>
                <th scope="col">{t('admin.category.productCount')}</th>
                <th scope="col">
                  <span className="sr-only">{t('common.actions')}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((category) =>
                editing === category.id ? (
                  <tr key={category.id}>
                    <td colSpan={4}>
                      <div className="form-row">
                        <TextField
                          label={t('admin.category.nameAz')}
                          value={editDraft.name_az}
                          onChange={(e) => setEditDraft({ ...editDraft, name_az: e.target.value })}
                        />
                        <TextField
                          label={t('admin.category.nameEn')}
                          value={editDraft.name_en}
                          onChange={(e) => setEditDraft({ ...editDraft, name_en: e.target.value })}
                        />
                        <SelectField
                          label={t('admin.category.parent')}
                          value={editDraft.parent_id}
                          onChange={(e) =>
                            setEditDraft({ ...editDraft, parent_id: e.target.value })
                          }
                        >
                          <option value="">{t('admin.category.none')}</option>
                          {roots
                            .filter((root) => root.id !== category.id)
                            .map((root) => (
                              <option key={root.id} value={root.id}>
                                {root.name_az}
                              </option>
                            ))}
                        </SelectField>
                      </div>
                      <CheckboxField
                        label={t('admin.category.active')}
                        checked={editDraft.is_active}
                        onChange={(e) =>
                          setEditDraft({ ...editDraft, is_active: e.target.checked })
                        }
                      />
                      <div className="row-actions">
                        <Button
                          variant="primary"
                          size="sm"
                          disabled={update.isPending}
                          onClick={() => update.mutate(category.id)}
                        >
                          <Check size={15} aria-hidden="true" />
                          {t('common.save')}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setEditing(null)}>
                          <X size={15} aria-hidden="true" />
                          {t('common.cancel')}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={category.id}>
                    <td>
                      <span style={{ paddingLeft: category.parent_id ? '1.25rem' : 0 }}>
                        {category.name_az}
                      </span>
                      {category.name_en && <Badge tone="neutral">EN</Badge>}
                      {!category.is_active && (
                        <Badge tone="warning">{t('admin.category.hidden')}</Badge>
                      )}
                    </td>
                    <td className="muted">{category.slug}</td>
                    <td className="tabular">{category.product_count}</td>
                    <td>
                      <div className="row-actions">
                        <Button
                          variant="ghost"
                          size="sm"
                          icon
                          aria-label={t('admin.category.editLabel', { name: category.name_az })}
                          onClick={() => startEdit(category)}
                        >
                          <Pencil size={15} aria-hidden="true" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          icon
                          aria-label={t('admin.category.deleteLabel', { name: category.name_az })}
                          disabled={remove.isPending}
                          onClick={() => remove.mutate(category)}
                        >
                          <Trash2 size={15} aria-hidden="true" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
