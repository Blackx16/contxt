// Contxt shared contract — TypeScript types for the SvelteKit web app + MV3 extension.
// Canonical source of truth is ./context_card.schema.json. Keep this file in sync with it
// and with ./models.py. Frozen contract: change all three together, or not at all.

export type Tier = "private" | "shared";

export type Source = "gmail" | "calendar" | "notion";

export type EntityType =
  | "person"
  | "org"
  | "date"
  | "money"
  | "location"
  | "email"
  | "phone"
  | "url"
  | "misc";

export interface Entity {
  type: EntityType;
  value: string;
}

/** Present only on PRIVATE cards at rest in the cloud blind relay (cloud never holds the key). */
export interface Encryption {
  alg: "AES-256-GCM";
  /** base64url-encoded 96-bit nonce */
  iv: string;
  /** base64url-encoded ciphertext of the card content JSON */
  ciphertext: string;
  /** Client-side key identifier (ECDH-derived). Never a raw key. */
  key_ref: string | null;
}

/**
 * One distilled unit of context.
 * SHARED cards are served over MCP as-is; PRIVATE cards are decrypted client-side
 * and never leave the device in plaintext. When `encryption` is set, `summary`/`body` are null.
 */
export interface ContextCard {
  id: string; // `card_<uuidv4>`
  tier: Tier;
  source: Source;
  title: string;
  summary: string | null;
  body: string | null;
  entities: Entity[];
  sensitivity_score: number; // 0..1
  created_at: string; // ISO 8601 / RFC 3339
  embedding_ref: string | null; // e.g. "vec:shared:00001"; null for PRIVATE or pre-index
  encryption?: Encryption | null;
  meta?: Record<string, unknown> | null;
}

/** What the Crown-Jewels Gateway emits per ingested item, before distillation. */
export interface TierDecision {
  tier: Tier;
  sensitivity_score: number; // 0..1
  categories: string[]; // "money", "kw:loan", Gemma categories, ...
  reason: string;
  source_ref?: string | null;
}

// ---- MCP tool I/O ----

export interface GetContextRequest {
  query: string;
  limit?: number; // default 8
}

export interface GetContextResponse {
  cards: ContextCard[]; // SHARED cards only on the browser/HTTP path
  query?: string;
  total?: number;
  private_withheld?: number; // SHARED-only browser path: PRIVATE matches withheld
  private_total?: number; // SHARED-only browser path: total PRIVATE on-device
}

export interface DraftReplyRequest {
  email: string;
  max_words?: number; // default 150
}

export interface DraftReplyResponse {
  draft: string;
  used_card_ids: string[];
  private_cards_excluded?: number; // PRIVATE cards retrieved locally but withheld from the cloud model
}
