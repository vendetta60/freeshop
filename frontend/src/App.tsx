import { QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router';

import { RootLayout } from '@/components/layout/RootLayout';
import { RouteFallback } from '@/components/layout/RouteFallback';
import { queryClient } from '@/lib/api/queryClient';

/**
 * Route-level code splitting from day one (plan.md 11). Adding pages must not
 * grow the initial bundle, and that only holds if the first route is lazy.
 */
const HomePage = lazy(() => import('@/pages/public/HomePage'));
const ProductsPage = lazy(() => import('@/pages/public/ProductsPage'));
const ProductDetailPage = lazy(() => import('@/pages/public/ProductDetailPage'));
const CartPage = lazy(() => import('@/pages/public/CartPage'));
const ContactPage = lazy(() => import('@/pages/public/ContactPage'));
const NotFoundPage = lazy(() => import('@/pages/public/NotFoundPage'));
const ProfilePage = lazy(() => import('@/pages/account/ProfilePage'));
const OrdersPage = lazy(() => import('@/pages/account/OrdersPage'));
const OrderDetailPage = lazy(() => import('@/pages/account/OrderDetailPage'));
const OfferPage = lazy(() => import('@/pages/account/OfferPage'));
const MyListingsPage = lazy(() => import('@/pages/account/MyListingsPage'));

/**
 * The community layer (FreeShop_Prompt 3-8). Lazy for the same reason as
 * everything else: a visitor who only browses the catalogue should never
 * download the message composer.
 */
const NeedsPage = lazy(() => import('@/pages/public/NeedsPage'));
const NeedDetailPage = lazy(() => import('@/pages/public/NeedDetailPage'));
const NeedFormPage = lazy(() => import('@/pages/account/NeedFormPage'));
const MyNeedsPage = lazy(() => import('@/pages/account/MyNeedsPage'));
const MessagesPage = lazy(() => import('@/pages/account/MessagesPage'));
const ConversationPage = lazy(() => import('@/pages/account/ConversationPage'));
const LoansPage = lazy(() => import('@/pages/account/LoansPage'));
const AidPage = lazy(() => import('@/pages/public/AidPage'));
const AidDetailPage = lazy(() => import('@/pages/public/AidDetailPage'));
const AidCommitmentsPage = lazy(() => import('@/pages/account/AidCommitmentsPage'));

/**
 * The admin panel is a separate lazy chunk per page, not one bundle: a
 * visitor who never signs in as an admin should never download the product
 * form, and the shell alone is what the guard needs (plan.md 11).
 */
const AdminLayout = lazy(() => import('@/pages/admin/AdminLayout'));
const AdminDashboard = lazy(() => import('@/pages/admin/AdminDashboard'));
const AdminQueue = lazy(() => import('@/pages/admin/AdminQueue'));
const AdminProducts = lazy(() => import('@/pages/admin/AdminProducts'));
const AdminProductForm = lazy(() => import('@/pages/admin/AdminProductForm'));
const AdminCategories = lazy(() => import('@/pages/admin/AdminCategories'));
const AdminRequests = lazy(() => import('@/pages/admin/AdminRequests'));
const AdminUsers = lazy(() => import('@/pages/admin/AdminUsers'));
const AdminSettings = lazy(() => import('@/pages/admin/AdminSettings'));
const AdminNeeds = lazy(() => import('@/pages/admin/AdminNeeds'));
const AdminAid = lazy(() => import('@/pages/admin/AdminAid'));
const AdminAidCase = lazy(() => import('@/pages/admin/AdminAidCase'));

/**
 * Development-only routes. `import.meta.env.DEV` is statically replaced at
 * build time, so this branch and the chunk it references are tree-shaken out
 * of production entirely (plan.md 9.11).
 */
const KitchenSink = import.meta.env.DEV ? lazy(() => import('@/pages/dev/KitchenSink')) : null;

function page(element: React.ReactNode) {
  return <Suspense fallback={<RouteFallback />}>{element}</Suspense>;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<RootLayout />}>
            <Route index element={page(<HomePage />)} />
            <Route path="products" element={page(<ProductsPage />)} />
            <Route path="products/:slug" element={page(<ProductDetailPage />)} />
            <Route path="cart" element={page(<CartPage />)} />
            <Route path="contact" element={page(<ContactPage />)} />
            <Route path="profile" element={page(<ProfilePage />)} />
            <Route path="profile/orders" element={page(<OrdersPage />)} />
            <Route path="profile/orders/:id" element={page(<OrderDetailPage />)} />
            <Route path="profile/listings" element={page(<MyListingsPage />)} />
            <Route path="offer" element={page(<OfferPage />)} />

            {/* `needs/new` is declared BEFORE `needs/:id` so the literal path
                is not swallowed by the parameter. */}
            <Route path="needs" element={page(<NeedsPage />)} />
            <Route path="needs/new" element={page(<NeedFormPage />)} />
            <Route path="needs/:id" element={page(<NeedDetailPage />)} />
            <Route path="profile/needs" element={page(<MyNeedsPage />)} />

            <Route path="messages" element={page(<MessagesPage />)} />
            <Route path="messages/:id" element={page(<ConversationPage />)} />

            <Route path="profile/loans" element={page(<LoansPage />)} />

            <Route path="aid" element={page(<AidPage />)} />
            <Route path="aid/:slug" element={page(<AidDetailPage />)} />
            <Route path="profile/aid" element={page(<AidCommitmentsPage />)} />

            <Route path="admin" element={page(<AdminLayout />)}>
              <Route index element={page(<AdminDashboard />)} />
              <Route path="queue" element={page(<AdminQueue />)} />
              <Route path="products" element={page(<AdminProducts />)} />
              <Route path="products/:id" element={page(<AdminProductForm />)} />
              <Route path="categories" element={page(<AdminCategories />)} />
              <Route path="requests" element={page(<AdminRequests />)} />
              <Route path="users" element={page(<AdminUsers />)} />
              <Route path="settings" element={page(<AdminSettings />)} />
              <Route path="needs" element={page(<AdminNeeds />)} />
              <Route path="aid" element={page(<AdminAid />)} />
              <Route path="aid/:id" element={page(<AdminAidCase />)} />
            </Route>
            {KitchenSink && <Route path="dev/kitchen-sink" element={page(<KitchenSink />)} />}
            <Route path="*" element={page(<NotFoundPage />)} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
