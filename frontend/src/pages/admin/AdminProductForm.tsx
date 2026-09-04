import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ImagePlus, Loader2, Star, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';

import { Button } from '@/components/ui/Button';
import { CheckboxField, SelectField, TextAreaField, TextField } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { adminApi, adminKeys, type AdminProduct, type ProductPayload } from '@/lib/api/admin';
import { ApiError, reasonOf } from '@/lib/api/client';
import { useT, type TranslateFn } from '@/lib/i18n';
import type { StockStatus } from '@/lib/api/catalogue';
import { toast } from '@/stores/toastStore';

type FormState = {
  title_az: string;
  title_en: string;
  description_az: string;
  description_en: string;
  price: string;
  old_price: string;
  category_id: string;
  stock_status: StockStatus;
  is_featured: boolean;
};

const EMPTY: FormState = {
  title_az: '',
  title_en: '',
  description_az: '',
  description_en: '',
  price: '',
  old_price: '',
  category_id: '',
  stock_status: 'available',
  is_featured: false,
};

/** Manat as typed ("489,90" or "489.90") to integer qəpik. Money never
 *  becomes a float on the way (plan.md 8). */
function toMinor(input: string): number | null {
  const cleaned = input.trim().replace(/\s/g, '').replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const [whole, fraction = ''] = cleaned.split('.');
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
}

function fromMinor(minor: number | null): string {
  if (minor === null) return '';
  return (minor / 100).toFixed(2).replace('.', ',');
}

function validate(form: FormState, t: TranslateFn): Partial<Record<keyof FormState, string>> {
  const errors: Partial<Record<keyof FormState, string>> = {};

  if (form.title_az.trim().length < 2) errors.title_az = t('admin.validation.title');
  if (toMinor(form.price) === null) errors.price = t('admin.validation.price');
  if (form.old_price.trim() && toMinor(form.old_price) === null) {
    errors.old_price = t('admin.validation.oldPrice');
  }
  const price = toMinor(form.price);
  const old = form.old_price.trim() ? toMinor(form.old_price) : null;
  if (price !== null && old !== null && old <= price) {
    // A "discount" that is not one renders a ribbon that lies to the visitor.
    errors.old_price = t('admin.validation.oldPriceHigher');
  }
  if (!form.category_id) errors.category_id = t('admin.validation.category');

  return errors;
}

/**
 * Create / edit a product.
 *
 * The EN tab NEVER blocks a save (plan.md 7.3): an empty translation falls
 * back to AZ everywhere, and a validation error there is how bilingual
 * catalogues end up abandoned. It is a hint, not a gate.
 */
export default function AdminProductForm() {
  const { t } = useT();
  const params = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const productId = params.id && params.id !== 'new' ? Number(params.id) : null;
  const isEdit = productId !== null;

  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [tab, setTab] = useState<'az' | 'en'>('az');
  const fileInput = useRef<HTMLInputElement>(null);

  const categories = useQuery({
    queryKey: adminKeys.categories(),
    queryFn: ({ signal }) => adminApi.categories(signal),
  });

  const existing = useQuery({
    queryKey: adminKeys.product(productId ?? 0),
    queryFn: ({ signal }) => adminApi.product(productId!, signal),
    enabled: isEdit,
  });

  // Load the record into the form exactly once per fetched product, so typing
  // is never overwritten by a background refetch.
  const loadedId = useRef<number | null>(null);
  useEffect(() => {
    const product = existing.data;
    if (!product || loadedId.current === product.id) return;
    loadedId.current = product.id;
    setForm({
      title_az: product.title_az,
      title_en: product.title_en ?? '',
      description_az: product.description_az,
      description_en: product.description_en ?? '',
      price: fromMinor(product.price_minor),
      old_price: fromMinor(product.old_price_minor),
      category_id: String(product.category_id),
      stock_status: product.stock_status,
      is_featured: product.is_featured,
    });
  }, [existing.data]);

  // Each child directly under its own parent. The API returns parents first
  // and then every child, which in a flat <select> puts "Mebel" nowhere near
  // "Ev və bağça" and makes the indent read as decoration.
  const orderedCategories = (categories.data ?? [])
    .filter((category) => category.parent_id === null)
    .flatMap((parent) => [
      parent,
      ...(categories.data ?? []).filter((child) => child.parent_id === parent.id),
    ]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const payload = (): ProductPayload => ({
    title_az: form.title_az.trim(),
    // null, not "", so the server CLEARS the column rather than storing an
    // empty string that would defeat the AZ fallback.
    title_en: form.title_en.trim() || null,
    description_az: form.description_az.trim(),
    description_en: form.description_en.trim() || null,
    price_minor: toMinor(form.price) ?? 0,
    old_price_minor: form.old_price.trim() ? toMinor(form.old_price) : null,
    category_id: Number(form.category_id),
    stock_status: form.stock_status,
    is_featured: form.is_featured,
  });

  const save = useMutation({
    mutationFn: async () =>
      isEdit ? adminApi.updateProduct(productId, payload()) : adminApi.createProduct(payload()),
    onSuccess: async (product: AdminProduct) => {
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      await queryClient.invalidateQueries({ queryKey: ['products'] });
      toast.success(isEdit ? t('admin.product.updated') : t('admin.product.created'));
      if (!isEdit) void navigate(`/admin/products/${product.id}`, { replace: true });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'PHONE_NOT_VERIFIED') {
        toast.error(t('admin.product.needsPhone'));
        return;
      }
      if (error instanceof ApiError && error.field) {
        setErrors((current) => ({ ...current, [error.field as keyof FormState]: error.message }));
      }
      toast.error(error instanceof ApiError ? error.message : t('admin.product.saveFailed'));
    },
  });

  const upload = useMutation({
    mutationFn: (files: File[]) => adminApi.uploadImages(productId!, files),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      toast.success(t('admin.product.imageUploaded'));
    },
    onError: (error) => {
      const message =
        {
          too_large: t('admin.upload.tooLarge'),
          too_many: t('admin.upload.tooMany'),
          not_an_image: t('admin.upload.notImage'),
          unsupported_format: t('admin.upload.unsupported'),
          undecodable: t('admin.upload.undecodable'),
        }[reasonOf(error)] ?? t('admin.upload.failed');
      toast.error(message);
    },
  });

  const imageAction = useMutation({
    mutationFn: async ({ id, action }: { id: number; action: 'main' | 'delete' }) => {
      if (action === 'main') {
        await adminApi.updateImage(productId!, id, { is_main: true });
        return;
      }
      await adminApi.deleteImage(productId!, id);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      await queryClient.invalidateQueries({ queryKey: ['products'] });
    },
    onError: () => toast.error(t('admin.product.imageFailed')),
  });

  const submit = () => {
    const found = validate(form, t);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      // Send focus to the tab that actually holds the problem, rather than
      // leaving an error announced on a panel nobody is looking at.
      setTab('az');
      toast.error(t('admin.product.formErrors'));
      return;
    }
    save.mutate();
  };

  if (isEdit && existing.isError) {
    return (
      <ErrorState title={t('admin.product.loadFailed')} onRetry={() => void existing.refetch()} />
    );
  }

  if (isEdit && existing.isPending) {
    return <Skeleton height={420} radius="var(--r-lg)" />;
  }

  const images = existing.data?.images ?? [];

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Link
            to="/admin/products"
            className="btn btn--ghost btn--sm btn--icon"
            aria-label={t('common.back')}
          >
            <ArrowLeft size={16} aria-hidden="true" />
          </Link>
          <h1 style={{ fontSize: '1.25rem' }}>
            {isEdit ? t('admin.product.edit') : t('admin.product.new')}
          </h1>
        </div>
        <Button variant="primary" size="sm" onClick={submit} disabled={save.isPending}>
          {save.isPending && <Loader2 size={15} className="spin" aria-hidden="true" />}
          {t('common.save')}
        </Button>
      </header>

      <div className="card admin__form">
        <div className="tabs" role="tablist" aria-label={t('admin.product.language')}>
          {(['az', 'en'] as const).map((code) => (
            <button
              key={code}
              type="button"
              role="tab"
              aria-selected={tab === code}
              className="tabs__tab"
              onClick={() => setTab(code)}
            >
              {code.toUpperCase()}
            </button>
          ))}
        </div>

        {tab === 'az' ? (
          <>
            <TextField
              label={t('admin.product.titleAz')}
              required
              value={form.title_az}
              error={errors.title_az}
              maxLength={200}
              onChange={(e) => set('title_az', e.target.value)}
            />
            <TextAreaField
              label={t('admin.product.descriptionAz')}
              rows={5}
              value={form.description_az}
              onChange={(e) => set('description_az', e.target.value)}
            />
          </>
        ) : (
          <>
            <TextField
              label={t('admin.product.titleEn')}
              value={form.title_en}
              maxLength={200}
              hint={t('admin.product.enTitleHint')}
              onChange={(e) => set('title_en', e.target.value)}
            />
            <TextAreaField
              label={t('admin.product.descriptionEn')}
              rows={5}
              value={form.description_en}
              hint={t('admin.product.enTextHint')}
              onChange={(e) => set('description_en', e.target.value)}
            />
          </>
        )}

        <div className="form-row">
          <TextField
            label={t('admin.product.priceField')}
            required
            inputMode="decimal"
            value={form.price}
            error={errors.price}
            placeholder="489,90"
            onChange={(e) => set('price', e.target.value)}
          />
          <TextField
            label={t('admin.product.oldPrice')}
            inputMode="decimal"
            value={form.old_price}
            error={errors.old_price}
            hint={t('admin.product.oldPriceHint')}
            onChange={(e) => set('old_price', e.target.value)}
          />
        </div>

        <div className="form-row">
          <SelectField
            label={t('admin.product.category')}
            //required
            value={form.category_id}
            //error={errors.category_id}
            onChange={(e) => set('category_id', e.target.value)}
          >
            <option value="">{t('admin.product.choose')}</option>
            {orderedCategories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.parent_id ? `— ${category.name_az}` : category.name_az}
              </option>
            ))}
          </SelectField>

          <SelectField
            label={t('admin.product.stock')}
            value={form.stock_status}
            onChange={(e) => set('stock_status', e.target.value as StockStatus)}
          >
            <option value="available">{t('stock.available')}</option>
            <option value="out_of_stock">{t('stock.out_of_stock')}</option>
            <option value="on_order">{t('stock.on_order')}</option>
          </SelectField>
        </div>

        <CheckboxField
          label={t('admin.product.featureIt')}
          checked={form.is_featured}
          onChange={(e) => set('is_featured', e.target.checked)}
        />
      </div>

      <div className="card admin__form">
        <h2 style={{ fontSize: '1rem' }}>{t('admin.product.images')}</h2>
        {!isEdit ? (
          <p className="muted">{t('admin.product.imagesAfterSave')}</p>
        ) : (
          <>
            <div className="image-grid">
              {images.map((image) => (
                <figure
                  key={image.id}
                  className={image.is_main ? 'image-tile image-tile--main' : 'image-tile'}
                >
                  <img src={image.url} alt="" loading="lazy" />
                  <figcaption className="image-tile__actions">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon
                      aria-label={t('admin.product.makeMain')}
                      aria-pressed={image.is_main}
                      disabled={image.is_main || imageAction.isPending}
                      onClick={() => imageAction.mutate({ id: image.id, action: 'main' })}
                    >
                      <Star size={14} aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon
                      aria-label={t('admin.product.deleteImage')}
                      disabled={imageAction.isPending}
                      onClick={() => imageAction.mutate({ id: image.id, action: 'delete' })}
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </Button>
                  </figcaption>
                </figure>
              ))}

              <button
                type="button"
                className="image-tile image-tile--add"
                onClick={() => fileInput.current?.click()}
                disabled={upload.isPending || images.length >= 8}
              >
                {upload.isPending ? (
                  <Loader2 size={20} className="spin" aria-hidden="true" />
                ) : (
                  <ImagePlus size={20} aria-hidden="true" />
                )}
                <span>
                  {images.length >= 8 ? t('admin.product.imageLimit') : t('admin.product.addImage')}
                </span>
              </button>
            </div>

            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                if (files.length) upload.mutate(files);
                // Reset, so re-picking the same file fires change again.
                e.target.value = '';
              }}
            />
            <p className="muted" style={{ fontSize: '0.8125rem' }}>
              {t('admin.product.imageHint')}
            </p>
          </>
        )}
      </div>
    </section>
  );
}
