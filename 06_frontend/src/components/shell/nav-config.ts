/**
 * Single source of truth for app navigation.
 *
 * Each module maps to a tennetctl feature number (architecture.md).
 * Items are grouped into named sections — the sidebar renders each group
 * with a label separator, so modules can scale to many pages.
 */

import {
  Shield,
  KeyRound,
  FileClock,
  Users,
  Building2,
  LayoutGrid,
  Lock,
  Unlock,
  Activity,
  ScrollText,
  UserCheck,
  UserX,
  FolderKey,
  Layers,
  GitBranch,
  Settings2,
  Globe,
  ShieldCheck,
  ClipboardList,
  BarChart3,
  Filter,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string; // e.g. "new", count string
};

export type NavGroup = {
  label: string; // section heading, e.g. "Identity"
  items: NavItem[];
};

export type NavModule = {
  key: string;
  number: string;
  label: string;
  href: string;
  icon: LucideIcon;
  description: string;
  groups: NavGroup[];
};

export const NAV_MODULES: NavModule[] = [
  {
    key: "iam",
    number: "03",
    label: "IAM",
    href: "/iam",
    icon: KeyRound,
    description: "Identity, users & access",
    groups: [
      {
        label: "Overview",
        items: [
          { label: "Dashboard",      href: "/iam",                icon: LayoutGrid },
        ],
      },
      {
        label: "Identity",
        items: [
          { label: "Users",          href: "/iam/users",          icon: Users },
          { label: "Active Users",   href: "/iam/users/active",   icon: UserCheck },
          { label: "Suspended",      href: "/iam/users/suspended",icon: UserX },
        ],
      },
      {
        label: "Tenancy",
        items: [
          { label: "Organizations",  href: "/iam/organizations",  icon: Building2 },
          { label: "Workspaces",     href: "/iam/workspaces",     icon: Layers },
          { label: "Memberships",    href: "/iam/memberships",    icon: GitBranch },
        ],
      },
      {
        label: "Access",
        items: [
          { label: "Sessions",       href: "/iam/sessions",       icon: Activity },
          { label: "Permissions",    href: "/iam/permissions",    icon: ShieldCheck },
          { label: "Roles",          href: "/iam/roles",          icon: FolderKey },
        ],
      },
      {
        label: "Config",
        items: [
          { label: "Settings",       href: "/iam/settings",       icon: Settings2 },
          { label: "Domains",        href: "/iam/domains",        icon: Globe },
        ],
      },
    ],
  },
  {
    key: "vault",
    number: "02",
    label: "Vault",
    href: "/vault",
    icon: Shield,
    description: "Secrets & KMS",
    groups: [
      {
        label: "Status",
        items: [
          { label: "Overview",       href: "/vault",              icon: Activity },
        ],
      },
      {
        label: "Operations",
        items: [
          { label: "Seal",           href: "/vault/seal",         icon: Lock },
          { label: "Unseal",         href: "/vault/unseal",       icon: Unlock },
        ],
      },
      {
        label: "Secrets",
        items: [
          { label: "Keys",           href: "/vault/keys",         icon: FolderKey },
          { label: "Settings",       href: "/vault/settings",     icon: Settings2 },
        ],
      },
    ],
  },
  {
    key: "audit",
    number: "04",
    label: "Audit",
    href: "/audit",
    icon: FileClock,
    description: "Append-only event log",
    groups: [
      {
        label: "Events",
        items: [
          { label: "All Events",     href: "/audit",              icon: ScrollText },
          { label: "By Category",    href: "/audit/categories",   icon: ClipboardList },
          { label: "Filters",        href: "/audit/filters",      icon: Filter },
        ],
      },
      {
        label: "Analytics",
        items: [
          { label: "Summary",        href: "/audit/summary",      icon: BarChart3 },
        ],
      },
    ],
  },
];

export function findModuleByPath(pathname: string): NavModule | undefined {
  return NAV_MODULES.find(
    (m) => pathname === m.href || pathname.startsWith(`${m.href}/`)
  );
}
