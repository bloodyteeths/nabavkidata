import { User } from './api';
import { useState, useEffect } from 'react';

export const ROLES = {
  ADMIN: 'admin',
  USER: 'user',
  MODERATOR: 'moderator',
} as const;

export const PERMISSIONS = {
  VIEW_ADMIN_PANEL: 'view_admin_panel',
  MANAGE_USERS: 'manage_users',
  MANAGE_TENDERS: 'manage_tenders',
  VIEW_ANALYTICS: 'view_analytics',
  MANAGE_SETTINGS: 'manage_settings',
  TRIGGER_SCRAPER: 'trigger_scraper',
  SEND_BROADCASTS: 'send_broadcasts',
  VIEW_LOGS: 'view_logs',
} as const;

export type Role = typeof ROLES[keyof typeof ROLES];
export type Permission = typeof PERMISSIONS[keyof typeof PERMISSIONS];

interface UserWithRole extends User {
  role?: string;
  permissions?: Permission[];
}

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  [ROLES.ADMIN]: [
    PERMISSIONS.VIEW_ADMIN_PANEL,
    PERMISSIONS.MANAGE_USERS,
    PERMISSIONS.MANAGE_TENDERS,
    PERMISSIONS.VIEW_ANALYTICS,
    PERMISSIONS.MANAGE_SETTINGS,
    PERMISSIONS.TRIGGER_SCRAPER,
    PERMISSIONS.SEND_BROADCASTS,
    PERMISSIONS.VIEW_LOGS,
  ],
  [ROLES.MODERATOR]: [
    PERMISSIONS.VIEW_ADMIN_PANEL,
    PERMISSIONS.MANAGE_TENDERS,
    PERMISSIONS.VIEW_ANALYTICS,
  ],
  [ROLES.USER]: [],
};

export function isAdmin(user: UserWithRole | null | undefined): boolean {
  if (!user) return false;
  return user.role === ROLES.ADMIN;
}

export function canAccessAdmin(user: UserWithRole | null | undefined): boolean {
  if (!user) return false;
  return user.role === ROLES.ADMIN || user.role === ROLES.MODERATOR;
}

export function hasPermission(user: UserWithRole | null | undefined, permission: Permission): boolean {
  if (!user) return false;

  // Check explicit permissions first
  if (user.permissions?.includes(permission)) return true;

  // Check role-based permissions
  const role = (user.role || ROLES.USER) as Role;
  return ROLE_PERMISSIONS[role]?.includes(permission) || false;
}

export function hasAnyPermission(user: UserWithRole | null | undefined, permissions: Permission[]): boolean {
  return permissions.some(permission => hasPermission(user, permission));
}

export function hasAllPermissions(user: UserWithRole | null | undefined, permissions: Permission[]): boolean {
  return permissions.every(permission => hasPermission(user, permission));
}

export function usePermissions(user: UserWithRole | null | undefined) {
  const [permissions, setPermissions] = useState<Permission[]>([]);

  useEffect(() => {
    if (!user) {
      setPermissions([]);
      return;
    }

    const role = (user.role || ROLES.USER) as Role;
    const rolePerms = ROLE_PERMISSIONS[role] || [];
    const userPerms = user.permissions || [];

    setPermissions([...new Set([...rolePerms, ...userPerms])]);
  }, [user]);

  return {
    permissions,
    isAdmin: isAdmin(user),
    canAccessAdmin: canAccessAdmin(user),
    hasPermission: (permission: Permission) => hasPermission(user, permission),
    hasAnyPermission: (perms: Permission[]) => hasAnyPermission(user, perms),
    hasAllPermissions: (perms: Permission[]) => hasAllPermissions(user, perms),
  };
}
