# Normalized Schema Design

## ER Diagram (Mermaid)

```mermaid
erDiagram
    USER ||--o{ PROJECT : "owns"
    USER {
        uuid id PK
        string email
        string password_hash
    }
    PROJECT ||--o{ ASSET : "contains"
    PROJECT {
        uuid id PK
        uuid user_id FK
        string name
        string description
    }
    ASSET {
        uuid id PK
        uuid project_id FK
        string type
        string url
    }
```

## Principles Applied
1. **1:N Relationships**: Users can have multiple projects, and projects can have multiple assets.
2. **Foreign Key Integrity**: `user_id` and `project_id` use `ON DELETE CASCADE` to maintain consistency.
3. **UUIDs**: Primary keys use UUIDs for better distribution and security.
