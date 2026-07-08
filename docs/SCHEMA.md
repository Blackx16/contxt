# Contxt — Context-card schema (the shared contract)

The single data contract every piece builds against (**CHA-15**). Canonical source:
[`schema/context_card.schema.json`](../schema/context_card.schema.json); mirrors in
[`schema/types.ts`](../schema/types.ts) (UI) and [`schema/models.py`](../schema/models.py)
(MCP + Gateway); mock data in [`schema/fixtures/`](../schema/fixtures/).

## Data shapes

```mermaid
erDiagram
    CONTEXT_CARD {
        string id PK "card_ + uuidv4"
        Tier tier "private or shared"
        Source source "gmail calendar notion"
        string title "1..200 chars"
        string summary "null if encrypted at rest"
        string body "nullable"
        Entity entities "0..N embedded"
        float sensitivity_score "0..1"
        datetime created_at "RFC3339 UTC"
        string embedding_ref "nullable vec:shared:N"
        Encryption encryption "nullable PRIVATE at rest"
        object meta "free-form"
    }
    ENTITY {
        EntityType type "person org date money etc"
        string value "non-empty"
    }
    ENCRYPTION {
        string alg "const AES-256-GCM"
        string iv "base64url 96-bit nonce"
        string ciphertext "base64url"
        string key_ref "nullable ECDH ref never a raw key"
    }
    TIER_DECISION {
        Tier tier "gateway emits per item"
        float sensitivity_score "0..1"
        string categories "string array rule kw gemma"
        string reason "justification"
        string source_ref "nullable"
    }
    GET_CONTEXT_REQUEST {
        string query "non-empty"
        int limit "default 8 range 1..50"
    }
    GET_CONTEXT_RESPONSE {
        ContextCard cards "SHARED only"
    }
    DRAFT_REPLY_REQUEST {
        string email "non-empty"
        int max_words "default 150"
    }
    DRAFT_REPLY_RESPONSE {
        string draft "reply text"
        string used_card_ids "string array"
    }
    CONTEXT_CARD ||--o{ ENTITY : "entities"
    CONTEXT_CARD ||--o| ENCRYPTION : "encryption"
    GET_CONTEXT_RESPONSE ||--o{ CONTEXT_CARD : "cards"
    TIER_DECISION ||--|| CONTEXT_CARD : "distilled into"
```

## Where each shape crosses a boundary

```mermaid
flowchart LR
    subgraph Ingest
        SRC[Gmail / Calendar / Notion]
    end
    subgraph Gateway [Crown-Jewels Gateway on-device]
        DEC{{TierDecision\ntier · sensitivity_score\ncategories · reason}}
    end
    subgraph Distill [Local / Cloud Gemma]
        CARD[ContextCard]
    end
    SRC --> DEC
    DEC -->|private| ENC[ContextCard + Encryption\nsummary/body = null]
    DEC -->|shared| SH[ContextCard\nplaintext summary]
    ENC --> RELAY[(Cloud blind relay\nciphertext only)]
    SH --> STORE[(Cloud store\nSHARED cards)]
    STORE --> MCP[[MCP get_context / draft_reply]]
    MCP -->|GetContextResponse.cards| AI[Any AI]
    RELAY -.decrypt on-device.-> LOCAL[Local model only]
```

## Design note — parse, don't validate

`tier` has **one** representation: the lowercase strings `"private"` / `"shared"`. The
`Tier` enum's *value* is the wire value, so parsing (raw → `Tier`) and serialization
(`Tier` → JSON) are exact inverses with no transform step. The Gateway boundary parses
once — `Tier._missing_` tolerates model/legacy casing like `"PRIVATE"` but canonicalizes
to the single form — so no code downstream re-checks or re-cases the tier.
(cf. Alexis King, [_Parse, don't validate_](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/).)
