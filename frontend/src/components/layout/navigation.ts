import {
  Award,
  BarChart3,
  Bell,
  BookOpen,
  Briefcase,
  CalendarDays,
  ClipboardCheck,
  FileText,
  FlaskConical,
  GraduationCap,
  HelpCircle,
  LayoutDashboard,
  Library,
  type LucideIcon,
  Megaphone,
  MessageSquare,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Star,
  Users,
} from 'lucide-react';

import type { Role } from '@/types';

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Roles that see this item. Empty means every signed-in role. */
  roles?: Role[];
  /** Extra permission gate on top of the role list. */
  permission?: string;
  section: 'main' | 'academic' | 'community' | 'admin';
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, section: 'main' },

  { label: 'Courses', href: '/courses', icon: BookOpen, section: 'academic', permission: 'course.view' },
  { label: 'Notes', href: '/notes', icon: FileText, section: 'academic', permission: 'note.view' },
  {
    label: 'Assignments',
    href: '/assignments',
    icon: ClipboardCheck,
    section: 'academic',
    permission: 'assignment.view',
  },
  {
    label: 'Attendance',
    href: '/attendance',
    icon: CalendarDays,
    section: 'academic',
    permission: 'attendance.view_own',
  },
  {
    label: 'Marks',
    href: '/marks',
    icon: GraduationCap,
    section: 'academic',
    permission: 'marks.view_own',
  },
  {
    label: 'Question bank',
    href: '/question-bank',
    icon: HelpCircle,
    section: 'academic',
    permission: 'question.view',
  },

  {
    label: 'Announcements',
    href: '/announcements',
    icon: Megaphone,
    section: 'community',
    permission: 'announcement.view',
  },
  { label: 'Calendar', href: '/calendar', icon: CalendarDays, section: 'community', permission: 'event.view' },
  {
    label: 'Discussions',
    href: '/discussions',
    icon: MessageSquare,
    section: 'community',
    permission: 'forum.participate',
  },
  {
    label: 'Analytics',
    href: '/analytics',
    icon: BarChart3,
    section: 'community',
    permission: 'analytics.view_course',
  },
  {
    label: 'Research',
    href: '/research',
    icon: FlaskConical,
    section: 'community',
    permission: 'research.view',
  },
  { label: 'Alumni', href: '/alumni', icon: Users, section: 'community', permission: 'alumni.view' },
  { label: 'Opportunities', href: '/jobs', icon: Briefcase, section: 'community', permission: 'job.view' },
  { label: 'E-resources', href: '/library', icon: Library, section: 'community', permission: 'library.view' },
  { label: 'Feedback', href: '/feedback', icon: Star, section: 'community', permission: 'feedback.submit' },
  {
    label: 'Certificates',
    href: '/certificates',
    icon: Award,
    section: 'community',
    permission: 'certificate.view',
  },

  { label: 'Users', href: '/admin/users', icon: Users, section: 'admin', permission: 'user.manage' },
  {
    label: 'Academic setup',
    href: '/admin/academics',
    icon: GraduationCap,
    section: 'admin',
    permission: 'academic.manage',
  },
  {
    label: 'Roles & permissions',
    href: '/admin/roles',
    icon: ShieldCheck,
    section: 'admin',
    permission: 'role.manage',
  },
  {
    label: 'Configuration',
    href: '/admin/settings',
    icon: SlidersHorizontal,
    section: 'admin',
    permission: 'settings.manage',
  },
  {
    label: 'Audit log',
    href: '/admin/audit',
    icon: ShieldCheck,
    section: 'admin',
    permission: 'audit.view',
  },
];

export const SECTION_LABELS: Record<NavItem['section'], string> = {
  main: '',
  academic: 'Academics',
  community: 'Engagement',
  admin: 'Administration',
};

/** The four destinations shown in the mobile bottom bar, per role. */
export const MOBILE_NAV: Record<Role, { label: string; href: string; icon: LucideIcon }[]> = {
  STUDENT: [
    { label: 'Home', href: '/dashboard', icon: LayoutDashboard },
    { label: 'Courses', href: '/courses', icon: BookOpen },
    { label: 'Work', href: '/assignments', icon: ClipboardCheck },
    { label: 'Marks', href: '/marks', icon: GraduationCap },
  ],
  FACULTY: [
    { label: 'Home', href: '/dashboard', icon: LayoutDashboard },
    { label: 'Courses', href: '/courses', icon: BookOpen },
    { label: 'Attendance', href: '/attendance', icon: CalendarDays },
    { label: 'Marks', href: '/marks', icon: GraduationCap },
  ],
  SCHOLAR: [
    { label: 'Home', href: '/dashboard', icon: LayoutDashboard },
    { label: 'Research', href: '/research', icon: FlaskConical },
    { label: 'Courses', href: '/courses', icon: BookOpen },
    { label: 'Alerts', href: '/notifications', icon: Bell },
  ],
  ADMIN: [
    { label: 'Home', href: '/dashboard', icon: LayoutDashboard },
    { label: 'Users', href: '/admin/users', icon: Users },
    { label: 'Courses', href: '/courses', icon: BookOpen },
    { label: 'Analytics', href: '/analytics', icon: BarChart3 },
  ],
  DEAN: [
    { label: 'Home', href: '/dashboard', icon: LayoutDashboard },
    { label: 'Analytics', href: '/analytics', icon: BarChart3 },
    { label: 'Courses', href: '/courses', icon: BookOpen },
    { label: 'Notices', href: '/announcements', icon: Megaphone },
  ],
  ALUMNI: [
    { label: 'Home', href: '/dashboard', icon: LayoutDashboard },
    { label: 'Jobs', href: '/jobs', icon: Briefcase },
    { label: 'Alumni', href: '/alumni', icon: Users },
    { label: 'Events', href: '/calendar', icon: CalendarDays },
  ],
};

export const SETTINGS_ITEM = { label: 'Settings', href: '/settings', icon: Settings };
