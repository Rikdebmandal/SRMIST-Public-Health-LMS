'use client';

import { useQuery } from '@tanstack/react-query';
import {
  Bell,
  ChevronDown,
  LogOut,
  Menu,
  Moon,
  Search,
  Settings as SettingsIcon,
  Sun,
  User as UserIcon,
  X,
} from 'lucide-react';
import { useTheme } from 'next-themes';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import {
  MOBILE_NAV,
  NAV_ITEMS,
  SECTION_LABELS,
  SETTINGS_ITEM,
  type NavItem,
} from '@/components/layout/navigation';
import { Avatar, Badge, Button, Input } from '@/components/ui';
import { api, toList } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useBranding } from '@/lib/branding';
import { cn, firstName } from '@/lib/utils';
import type { NotificationItem } from '@/types';

interface SearchResult {
  type: string;
  id: string;
  title: string;
  subtitle: string;
  link: string;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, loading, signOut, can } = useAuth();
  const branding = useBranding();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace('/login');
  }, [loading, user, router]);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setSidebarOpen(false), [pathname]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading your workspace…</p>
        </div>
      </div>
    );
  }

  if (!user) return null;

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.roles && !item.roles.includes(user.role)) return false;
    if (item.permission && !can(item.permission)) return false;
    return true;
  });

  const sections: NavItem['section'][] = ['main', 'academic', 'community', 'admin'];
  const mobileItems = MOBILE_NAV[user.role] ?? MOBILE_NAV.STUDENT;

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-card lg:flex">
        <BrandBlock branding={branding} />
        <nav
          aria-label="Main navigation"
          className="scrollbar-thin flex-1 overflow-y-auto px-3 py-3"
        >
          {sections.map((section) => {
            const items = visibleItems.filter((item) => item.section === section);
            if (items.length === 0) return null;
            return (
              <div key={section} className="mb-4">
                {SECTION_LABELS[section] && (
                  <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {SECTION_LABELS[section]}
                  </p>
                )}
                <ul className="space-y-0.5">
                  {items.map((item) => (
                    <NavLink key={item.href} item={item} pathname={pathname} />
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>
        <div className="border-t border-border p-3">
          <NavLink
            item={{ ...SETTINGS_ITEM, section: 'main' } as NavItem}
            pathname={pathname}
            asListItem={false}
          />
        </div>
      </aside>

      {/* Mobile drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setSidebarOpen(false)}
            aria-hidden
          />
          <aside
            className="relative flex h-full w-72 max-w-[85vw] flex-col bg-card shadow-xl"
            aria-label="Main navigation"
          >
            <div className="flex items-center justify-between border-b border-border p-3">
              <BrandBlock branding={branding} compact />
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                aria-label="Close navigation"
                className="rounded-md p-2 hover:bg-muted"
              >
                <X className="h-5 w-5" aria-hidden />
              </button>
            </div>
            <nav className="scrollbar-thin flex-1 overflow-y-auto px-3 py-3">
              {sections.map((section) => {
                const items = visibleItems.filter((item) => item.section === section);
                if (items.length === 0) return null;
                return (
                  <div key={section} className="mb-4">
                    {SECTION_LABELS[section] && (
                      <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                        {SECTION_LABELS[section]}
                      </p>
                    )}
                    <ul className="space-y-0.5">
                      {items.map((item) => (
                        <NavLink key={item.href} item={item} pathname={pathname} />
                      ))}
                    </ul>
                  </div>
                );
              })}
              <NavLink
                item={{ ...SETTINGS_ITEM, section: 'main' } as NavItem}
                pathname={pathname}
                asListItem={false}
              />
            </nav>
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenu={() => setSidebarOpen(true)} onSignOut={signOut} />
        <main
          id="main-content"
          className="flex-1 px-4 py-5 pb-24 sm:px-6 lg:px-8 lg:pb-8"
          tabIndex={-1}
        >
          <div className="mx-auto w-full max-w-[1400px] animate-fade-in">{children}</div>
        </main>
        <footer className="hidden border-t border-border px-6 py-4 text-xs text-muted-foreground lg:block">
          <p>{branding.footer_text}</p>
          <p className="mt-0.5">
            {branding.institution_name} · Demonstration data only — no real student records.
          </p>
        </footer>
      </div>

      {/* Mobile bottom navigation */}
      <nav
        aria-label="Quick navigation"
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-border bg-card/95 backdrop-blur lg:hidden"
      >
        {mobileItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex min-h-[56px] flex-col items-center justify-center gap-0.5 px-1 py-2 text-[11px] font-medium transition-colors',
                active ? 'text-primary' : 'text-muted-foreground',
              )}
            >
              <item.icon className="h-5 w-5" aria-hidden />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function BrandBlock({
  branding,
  compact,
}: {
  branding: ReturnType<typeof useBranding>;
  compact?: boolean;
}) {
  return (
    <Link
      href="/dashboard"
      className={cn(
        'flex items-center gap-2.5 border-border px-4 py-4',
        !compact && 'border-b',
      )}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
        PH
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold leading-tight">
          {branding.platform_name}
        </span>
        <span className="block truncate text-[11px] leading-tight text-muted-foreground">
          {branding.school_name}
        </span>
      </span>
    </Link>
  );
}

function NavLink({
  item,
  pathname,
  asListItem = true,
}: {
  item: NavItem;
  pathname: string;
  asListItem?: boolean;
}) {
  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
  const link = (
    <Link
      href={item.href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
        active
          ? 'bg-primary/10 text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      <item.icon className="h-4 w-4 shrink-0" aria-hidden />
      <span className="truncate">{item.label}</span>
    </Link>
  );
  return asListItem ? <li>{link}</li> : link;
}

function TopBar({ onMenu, onSignOut }: { onMenu: () => void; onSignOut: () => void }) {
  const { user } = useAuth();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const { data: notifications } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => api.get<{ count: number }>('/notifications/unread-count'),
    refetchInterval: 60_000,
  });

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex h-14 items-center gap-2 px-4 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={onMenu}
          aria-label="Open navigation"
          className="rounded-md p-2 hover:bg-muted lg:hidden"
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>

        <div className="hidden flex-1 sm:block">
          <GlobalSearch />
        </div>
        <div className="flex-1 sm:hidden" />

        <button
          type="button"
          onClick={() => setSearchOpen((open) => !open)}
          aria-label="Search"
          aria-expanded={searchOpen}
          className="rounded-md p-2 hover:bg-muted sm:hidden"
        >
          <Search className="h-5 w-5" aria-hidden />
        </button>

        {mounted && (
          <button
            type="button"
            onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
            aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} theme`}
            className="rounded-md p-2 hover:bg-muted"
          >
            {resolvedTheme === 'dark' ? (
              <Sun className="h-5 w-5" aria-hidden />
            ) : (
              <Moon className="h-5 w-5" aria-hidden />
            )}
          </button>
        )}

        <Link
          href="/notifications"
          aria-label={`Notifications${notifications?.count ? ` (${notifications.count} unread)` : ''}`}
          className="relative rounded-md p-2 hover:bg-muted"
        >
          <Bell className="h-5 w-5" aria-hidden />
          {Boolean(notifications?.count) && (
            <span className="absolute right-1 top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
              {notifications!.count > 9 ? '9+' : notifications!.count}
            </span>
          )}
        </Link>

        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="flex items-center gap-2 rounded-md p-1 pr-2 hover:bg-muted"
          >
            <Avatar name={user?.full_name ?? ''} src={user?.avatar} size="sm" />
            <span className="hidden text-sm font-medium md:inline">
              {firstName(user?.full_name)}
            </span>
            <ChevronDown className="hidden h-4 w-4 text-muted-foreground md:inline" aria-hidden />
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full z-40 mt-1 w-60 rounded-lg border border-border bg-card p-1 shadow-lg"
            >
              <div className="border-b border-border px-3 py-2">
                <p className="truncate text-sm font-medium">{user?.full_name}</p>
                <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
                <Badge tone="muted" className="mt-1.5">
                  {user?.role_display}
                </Badge>
              </div>
              <Link
                href="/profile"
                role="menuitem"
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
                onClick={() => setMenuOpen(false)}
              >
                <UserIcon className="h-4 w-4" aria-hidden />
                My profile
              </Link>
              <Link
                href="/settings"
                role="menuitem"
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
                onClick={() => setMenuOpen(false)}
              >
                <SettingsIcon className="h-4 w-4" aria-hidden />
                Preferences
              </Link>
              <button
                type="button"
                role="menuitem"
                onClick={onSignOut}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-destructive hover:bg-destructive/10"
              >
                <LogOut className="h-4 w-4" aria-hidden />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>

      {searchOpen && (
        <div className="border-t border-border p-3 sm:hidden">
          <GlobalSearch autoFocus />
        </div>
      )}
    </header>
  );
}

function GlobalSearch({ autoFocus }: { autoFocus?: boolean }) {
  const [term, setTerm] = useState('');
  const [debounced, setDebounced] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term), 280);
    return () => clearTimeout(timer);
  }, [term]);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const { data, isFetching } = useQuery({
    queryKey: ['search', debounced],
    queryFn: () =>
      api.get<{ query: string; total: number; results: SearchResult[] }>(
        `/search?q=${encodeURIComponent(debounced)}`,
      ),
    enabled: debounced.trim().length >= 2,
  });

  return (
    <div className="relative max-w-md" ref={containerRef}>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        type="search"
        value={term}
        autoFocus={autoFocus}
        onChange={(event) => {
          setTerm(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Search courses, notes, announcements…"
        aria-label="Search the platform"
        className="h-9 pl-9"
      />
      {open && debounced.trim().length >= 2 && (
        <div className="absolute left-0 right-0 top-full z-40 mt-1 max-h-80 overflow-y-auto rounded-lg border border-border bg-card p-1 shadow-lg">
          {isFetching && (
            <p className="px-3 py-2 text-sm text-muted-foreground">Searching…</p>
          )}
          {!isFetching && data && data.results.length === 0 && (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              Nothing found for “{data.query}”.
            </p>
          )}
          {data?.results.map((result) => (
            <Link
              key={`${result.type}-${result.id}`}
              href={result.link}
              onClick={() => setOpen(false)}
              className="flex items-start gap-2 rounded-md px-3 py-2 hover:bg-muted"
            >
              <Badge tone="muted" className="mt-0.5 shrink-0 capitalize">
                {result.type}
              </Badge>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{result.title}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {result.subtitle}
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
