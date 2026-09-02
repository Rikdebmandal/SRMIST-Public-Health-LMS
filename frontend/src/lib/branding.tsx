'use client';

/**
 * Branding is database-driven: the institution name, colours and footer all
 * come from public system settings, so a deployment can be re-skinned without
 * a code change (brief sections 42 and 48).
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

import { API_BASE } from '@/lib/api';

export interface Branding {
  institution_name: string;
  school_name: string;
  platform_name: string;
  primary_color: string;
  secondary_color: string;
  logo_url: string;
  footer_text: string;
  support_email: string;
  default_theme: string;
}

const FALLBACK: Branding = {
  institution_name: 'SRM Institute of Science and Technology',
  school_name: 'School of Public Health',
  platform_name: 'Public Health LMS',
  primary_color: '#0b4f6c',
  secondary_color: '#1c7c54',
  logo_url: '',
  footer_text: 'Public Health LMS — School of Public Health',
  support_email: '',
  default_theme: 'system',
};

const BrandingContext = createContext<Branding>(FALLBACK);

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<Branding>(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/settings/public`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (data && !cancelled) setBranding({ ...FALLBACK, ...data });
      })
      .catch(() => {
        /* fall back to the built-in defaults */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <BrandingContext.Provider value={branding}>{children}</BrandingContext.Provider>;
}

export function useBranding() {
  return useContext(BrandingContext);
}
