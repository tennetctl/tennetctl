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
  org_id: string;
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
