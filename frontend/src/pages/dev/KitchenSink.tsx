import { Check, Plus, ShoppingBag, Trash2 } from 'lucide-react';

import { ProductCard } from '@/components/product/ProductCard';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { ProductCardSkeleton, Skeleton } from '@/components/ui/Skeleton';
import { useGlassTier } from '@/lib/hooks/useGlassTier';
import type { ProductSummary } from '@/components/product/ProductCard';
import { formatPrice } from '@/lib/utils/format';

/**
 * Kitchen sink - the design-system proof surface (plan.md 13, phase 1).
 *
 * Every primitive rendered in one place so all four accent x theme
 * combinations, plus reduced-transparency and reduced-motion, can be checked
 * at a glance. Development only; never routed in a production build.
 */

/** A local sample: the kitchen sink must render without a server, and its
 *  job is to exercise geometry, not to be real data. Ratios are deliberately
 *  extreme so the `object-fit: contain` rule is visible. */
const SAMPLE: ProductSummary[] = [
  {
    id: 1,
    slug: 'wide',
    title: 'Qoz ağacından əl işi jurnal masası, yumşaq kətan örtüklü oturacaqla birlikdə',
    price_minor: 48900,
    old_price_minor: null,
    currency: 'AZN',
    stock_status: 'available',
    category_id: 1,
    category_name: 'Mebel',
    image:
      'https://images.unsplash.com/photo-1550581190-9c1c48d21d6c?w=1200&h=800&q=75&auto=format&fit=crop',
    image_width: 1200,
    image_height: 800,
    is_featured: false,
  },
  {
    id: 2,
    slug: 'tall',
    title: 'Mis asma çıraq',
    price_minor: 21450,
    old_price_minor: 27900,
    currency: 'AZN',
    stock_status: 'available',
    category_id: 2,
    category_name: 'İşıqlandırma',
    image:
      'https://images.unsplash.com/photo-1540932239986-30128078f3c5?w=800&h=1200&q=75&auto=format&fit=crop',
    image_width: 800,
    image_height: 1200,
    is_featured: false,
  },
  {
    id: 3,
    slug: 'sold',
    title: 'Divar saatı',
    price_minor: 12500,
    old_price_minor: null,
    currency: 'AZN',
    stock_status: 'out_of_stock',
    category_id: 3,
    category_name: 'Dekorasiya',
    image:
      'https://images.unsplash.com/photo-1533090161767-e6ffed986c88?w=1000&h=1000&q=75&auto=format&fit=crop',
    image_width: 1000,
    image_height: 1000,
    is_featured: false,
  },
  {
    id: 4,
    slug: 'noimage',
    title: 'Şəkilsiz məhsul nümunəsi',
    price_minor: 86000,
    old_price_minor: null,
    currency: 'AZN',
    stock_status: 'on_order',
    category_id: 4,
    category_name: 'Tekstil',
    image: null,
    image_width: null,
    image_height: null,
    is_featured: false,
  },
];

const SURFACE_TOKENS = [
  '--bg',
  '--bg-elevated',
  '--surface',
  '--surface-2',
  '--surface-3',
  '--border',
  '--border-strong',
];
const TEXT_TOKENS = ['--text', '--text-muted', '--text-subtle'];
const ACCENT_TOKENS = [
  '--accent',
  '--accent-hover',
  '--accent-active',
  '--accent-subtle',
  '--accent-border',
];
const SEMANTIC_TOKENS = ['--success', '--warning', '--danger'];

function Swatches({ tokens }: { tokens: string[] }) {
  return (
    <div className="ks-swatches">
      {tokens.map((token) => (
        <div key={token} className="ks-swatch">
          <div className="ks-swatch__chip" style={{ background: `var(${token})` }} />
          <div className="ks-swatch__name">{token}</div>
        </div>
      ))}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="ks-section">
      <h2 style={{ fontSize: '1.0625rem', marginBottom: '0.75rem' }}>{title}</h2>
      {children}
    </section>
  );
}

export default function KitchenSink() {
  const tier = useGlassTier();

  return (
    <>
      <div className="hero" style={{ paddingBottom: '1rem' }}>
        <h1>Kitchen sink</h1>
        <p>
          Dizayn sisteminin bütün elementləri. Yuxarıdakı düymələrlə mövzunu və vurğu rəngini
          dəyişin — hər dörd kombinasiya burada yoxlanılır.
        </p>
        <p className="subtle" style={{ fontSize: '0.875rem' }}>
          Aktiv şüşə səviyyəsi (glass tier): <strong>{tier}</strong>
        </p>
      </div>

      <Section title="Rəng tokenləri">
        <p className="ks-label">Səthlər</p>
        <Swatches tokens={SURFACE_TOKENS} />
        <p className="ks-label" style={{ marginTop: '1rem' }}>
          Mətn
        </p>
        <Swatches tokens={TEXT_TOKENS} />
        <p className="ks-label" style={{ marginTop: '1rem' }}>
          Vurğu (eyni anda yalnız bir ton)
        </p>
        <Swatches tokens={ACCENT_TOKENS} />
        <p className="ks-label" style={{ marginTop: '1rem' }}>
          Semantik (qəsdən solğun)
        </p>
        <Swatches tokens={SEMANTIC_TOKENS} />
      </Section>

      <Section title="Şüşə səthlər">
        <p className="muted" style={{ fontSize: '0.875rem', marginBottom: '0.875rem' }}>
          Şüşə həmişə şəkil və ya məzmunun üzərində olur — heç vaxt düz fonun üzərində. Aşağıdakı
          rəngli fon qəsdən aqressivdir: kontrast ən pis hal üçün yoxlanmalıdır.
        </p>
        <div className="ks-glass-stage">
          <div
            className="glass glass--specular"
            style={{ padding: '1.25rem', maxWidth: 420, marginBottom: '1rem' }}
          >
            <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Standart şüşə</p>
            <p className="muted" style={{ fontSize: '0.875rem' }}>
              backdrop-filter: blur(20px) saturate(180%)
            </p>
          </div>
          <div
            className="glass glass--specular glass--deep"
            style={{ padding: '1.25rem', maxWidth: 420 }}
          >
            <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Dərin şüşə</p>
            <p className="muted" style={{ fontSize: '0.875rem' }}>
              Şəkil üzərində mətn üçün — kontrast tələbini ödəyir.
            </p>
          </div>
        </div>
      </Section>

      <Section title="Düymələr">
        <div className="ks-row">
          <Button variant="primary">Səbətə at</Button>
          <Button variant="secondary">Ətraflı</Button>
          <Button variant="ghost">Ləğv et</Button>
          <Button variant="danger">Sil</Button>
          <Button variant="primary" disabled>
            Deaktiv
          </Button>
        </div>
        <div className="ks-row">
          <Button variant="primary" size="sm">
            <Plus size={15} aria-hidden="true" />
            Kiçik
          </Button>
          <Button variant="primary" size="md">
            <ShoppingBag size={16} aria-hidden="true" />
            Orta
          </Button>
          <Button variant="primary" size="lg">
            <Check size={17} aria-hidden="true" />
            Böyük
          </Button>
          <Button variant="secondary" icon aria-label="Sil">
            <Trash2 size={16} aria-hidden="true" />
          </Button>
        </div>
      </Section>

      <Section title="Çiplər və nişanlar">
        <div className="ks-row">
          <Chip active>Hamısı</Chip>
          <Chip>Mebel</Chip>
          <Chip>Mətbəx</Chip>
          <Chip>Dekorasiya</Chip>
        </div>
        <div className="ks-row">
          <Badge tone="neutral">Neytral</Badge>
          <Badge tone="accent">Vurğu</Badge>
          <Badge tone="success">Uğurlu</Badge>
          <Badge tone="warning">Xəbərdarlıq</Badge>
          <Badge tone="danger">Xəta</Badge>
        </div>
      </Section>

      <Section title="Formalar">
        <div style={{ display: 'grid', gap: '0.75rem', maxWidth: 360 }}>
          <label htmlFor="ks-name" className="ks-label" style={{ marginBottom: 0 }}>
            Ad
          </label>
          <input id="ks-name" className="input" placeholder="Adınızı yazın" />
          <label htmlFor="ks-phone" className="ks-label" style={{ marginBottom: 0 }}>
            Nömrə (xətalı vəziyyət)
          </label>
          <input id="ks-phone" className="input" aria-invalid="true" defaultValue="+994 50" />
          <p style={{ color: 'var(--danger)', fontSize: '0.8125rem' }}>Nömrə tam deyil</p>
        </div>
      </Section>

      <Section title="Rəqəmlər (tabular-nums)">
        <table style={{ borderCollapse: 'collapse', fontSize: '0.9375rem' }}>
          <tbody>
            {[50, 245000, 1250000, 3200, 86000].map((minor) => (
              <tr key={minor}>
                <td className="tabular" style={{ padding: '0.25rem 1.5rem 0.25rem 0' }}>
                  {formatPrice(minor, 'az')}
                </td>
                <td className="tabular muted" style={{ padding: '0.25rem 0' }}>
                  {formatPrice(minor, 'en')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="subtle" style={{ fontSize: '0.8125rem', marginTop: '0.5rem' }}>
          Sütunlar düzülür, çünki rəqəmlər eyni enlidədir. AZ və EN formatları Intl ilə.
        </p>
      </Section>

      <Section title="Məhsul kartları — qarışıq kataloq">
        <p className="muted" style={{ fontSize: '0.875rem', marginBottom: '0.875rem' }}>
          Şəkillərin ölçüləri qəsdən çox fərqlidir (3000×2000-dən 400×400-ə). <code>contain</code>{' '}
          sayəsində məhsul heç vaxt kəsilmir və kartlar eyni hündürlükdə qalır.
        </p>
        <div className="product-grid">
          {SAMPLE.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </Section>

      <Section title="Yüklənmə vəziyyəti">
        <div className="product-grid">
          <ProductCardSkeleton />
          <ProductCardSkeleton />
          <div style={{ display: 'grid', gap: '0.6rem', alignContent: 'start' }}>
            <Skeleton width="100%" height={16} />
            <Skeleton width="80%" height={16} />
            <Skeleton width="60%" height={16} />
            <Skeleton width="90%" height={16} />
          </div>
        </div>
      </Section>
    </>
  );
}
