/**
 * Shared TypeScript types for all tennetctl API responses.
 * Every response follows the {ok, data} or {ok, error} envelope.
 */

// ---------------------------------------------------------------------------
// Envelope
// ---------------------------------------------------------------------------

export interface ApiOk<T> {
  ok: true;
  data: T;
}

export interface ApiError {
  ok: false;
  error: {
    code: string;
    message: string;
  };
}

export type ApiResponse<T> = ApiOk<T> | ApiError;

// ---------------------------------------------------------------------------
// Vault
// ---------------------------------------------------------------------------

export interface VaultStatus {
  initialized: boolean;
  status: "sealed" | "unsealed";
  unseal_mode: "manual" | "kms_azure" | "unknown";
  initialized_at: string | null;
}

// ---------------------------------------------------------------------------
// Sessions (auth)
// ---------------------------------------------------------------------------

export interface TokenPair {
  access_token: string;
  token_type: "bearer";
  refresh_token: string;
  expires_in: number;
  session_id: string;
}

export interface MeData {
  user_id: string;
  username: string | null;
  email: string | null;
  account_type: string;
  session_id: string;
}

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export interface UserData {
  id: string;
  account_type: string;
  auth_type: string;
  username: string | null;
  email: string | null;
  is_active: boolean;
  is_deleted: boolean;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface UserListData {
  items: UserData[];
  total: number;
}

// ---------------------------------------------------------------------------
// Groups
// ---------------------------------------------------------------------------

export interface GroupData {
  id: string;
  org_id: string;
  name: string | null;
  slug: string | null;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
  is_deleted: boolean;
  member_count: number;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface GroupListData {
  items: GroupData[];
  total: number;
}

export interface GroupMemberData {
  id: string;
  group_id: string;
  user_id: string;
  added_by: string;
  is_active: boolean;
  added_at: string;
  username: string | null;
  email: string | null;
}

export interface GroupMemberListData {
  items: GroupMemberData[];
  total: number;
}

// ---------------------------------------------------------------------------
// Products
// ---------------------------------------------------------------------------

export interface ProductData {
  id: string;
  name: string;
  code: string;
  category: string;
  is_sellable: boolean;
  is_active: boolean;
  is_deleted: boolean;
  description: string | null;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface ProductListData {
  items: ProductData[];
  total: number;
}

// ---------------------------------------------------------------------------
// Features
// ---------------------------------------------------------------------------

export interface FeatureData {
  id: string;
  code: string;
  name: string;
  scope: string;
  category: string;
  product_id: string | null;
  product_code: string | null;
  product_name: string | null;
  is_active: boolean;
  is_deleted: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeatureListData {
  items: FeatureData[];
  total: number;
}

export interface FeatureFilters {
  product_id?: string;
  scope?: string;
  category?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// RBAC
// ---------------------------------------------------------------------------

export interface PlatformRoleData {
  id: string;
  name: string;
  code: string;
  category: string;
  is_system: boolean;
  is_active: boolean;
  is_deleted: boolean;
  description: string | null;
  permission_count: number;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface PlatformRoleListData {
  items: PlatformRoleData[];
  total: number;
}

export interface OrgRoleData {
  id: string;
  org_id: string;
  name: string;
  code: string;
  category: string;
  is_system: boolean;
  is_active: boolean;
  is_deleted: boolean;
  description: string | null;
  permission_count: number;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface OrgRoleListData {
  items: OrgRoleData[];
  total: number;
}

export interface WorkspaceRoleData {
  id: string;
  workspace_id: string;
  name: string;
  code: string;
  category: string;
  is_system: boolean;
  is_active: boolean;
  is_deleted: boolean;
  description: string | null;
  permission_count: number;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceRoleListData {
  items: WorkspaceRoleData[];
  total: number;
}

export interface PermissionData {
  id: string;
  resource: string;
  action: string;
  code: string;
  description: string | null;
  is_active: boolean;
}

export interface PermissionListData {
  items: PermissionData[];
  total: number;
}

export interface RolePermissionData {
  id: string;
  role_id: string;
  permission_id: string;
  resource: string;
  action: string;
  code: string;
}

export interface RolePermissionListData {
  items: RolePermissionData[];
  total: number;
}

export interface UserPlatformRoleData {
  id: string;
  user_id: string;
  role_id: string;
  role_name: string;
  role_code: string;
  assigned_by: string;
  assigned_at: string;
}

export interface UserOrgRoleData {
  id: string;
  user_id: string;
  org_id: string;
  role_id: string;
  role_name: string;
  role_code: string;
  assigned_by: string;
  assigned_at: string;
}

export interface RbacCheckResult {
  allowed: boolean;
  permission: string;
  reason: string | null;
}

export interface EffectivePermissionsData {
  user_id: string;
  permissions: string[];
}

// ---------------------------------------------------------------------------
// Feature Flags
// ---------------------------------------------------------------------------

export interface FeatureFlagData {
  id: string;
  code: string;
  name: string;
  product_id: string | null;
  product_code: string | null;
  product_name: string | null;
  scope: "platform" | "org" | "workspace";
  category: string;
  flag_type: "boolean" | "kill_switch" | "experiment" | "rollout";
  default_value: unknown;
  status: "draft" | "active" | "deprecated" | "archived";
  is_active: boolean;
  is_deleted: boolean;
  description: string | null;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface FeatureFlagListData {
  items: FeatureFlagData[];
  total: number;
}

export interface FlagEnvironmentData {
  id: string;
  flag_id: string;
  environment: "dev" | "staging" | "prod";
  enabled: boolean;
  value: unknown;
  created_at: string;
  updated_at: string;
}

export interface FlagEnvironmentListData {
  items: FlagEnvironmentData[];
  total: number;
}

export interface FlagTargetData {
  id: string;
  flag_id: string;
  target_type: "org" | "workspace" | "user";
  target_id: string;
  enabled: boolean;
  value: unknown;
  created_at: string;
}

export interface FlagTargetListData {
  items: FlagTargetData[];
  total: number;
}

export interface FlagEvalResult {
  flag_code: string;
  enabled: boolean;
  value: unknown;
  source: string;
}

export interface FlagBootstrapData {
  flags: Record<string, FlagEvalResult>;
}

export interface FeatureFlagFilters {
  product_id?: string;
  scope?: string;
  status?: string;
  flag_type?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export interface AuditEvent {
  id: string;
  org_id: string | null;
  workspace_id: string | null;
  user_id: string | null;
  session_id: string | null;
  category: string;
  action: string;
  outcome: string;
  actor_id: string | null;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditListData {
  items: AuditEvent[];
  total: number;
}

export interface AuditFilters {
  limit?: number;
  offset?: number;
  org_id?: string;
  user_id?: string;
  session_id?: string;
  category?: string;
  action?: string;
  outcome?: string;
}
