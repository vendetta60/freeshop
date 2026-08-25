import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from '@/App';
import { initLang } from '@/lib/i18n';
import { loadSiteConfig } from '@/lib/site/config';
import { bootstrapAuth } from '@/stores/authStore';
import '@/styles/index.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('#root is missing from index.html');
}

// Both boot fetches run together: the session refresh (so a signed-in
// visitor never sees a flash of the signed-out UI) and the site config (so
// the admin's accent, theme and default language are in place before the
// first paint rather than snapping in after it).
void Promise.allSettled([loadSiteConfig(), bootstrapAuth()])
  // The language dictionary is resolved before render too, so a visitor whose
  // language is EN never sees a frame of Azerbaijani.
  .then(() => initLang())
  .finally(() => {
    createRoot(container).render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
  });
