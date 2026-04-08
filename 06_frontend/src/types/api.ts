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
