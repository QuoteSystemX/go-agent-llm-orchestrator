# Architecture: [Feature / Product Name]

> Version: 0.1 | Status: DRAFT | Linked PRD: wiki/PRD.md | Date: YYYY-MM-DD

---

## 1. System Context

_How does this feature fit into the existing system? What external systems does it interact with?_

```
[User] → [This Component] → [Downstream Service]
                          → [Database]
```

## 2. Components

| Component | Responsibility | Technology | Package/Path |
|-----------|---------------|------------|--------------|
|           |               |            |              |

## 3. Data Flow

_Sequence: request → processing → storage → response._

```
1. Client sends POST /endpoint
2. Handler validates input (see ADR-001)
3. Service processes business logic
4. Repository writes to DB
5. Response returned
```

## 4. Architecture Decision Records (ADRs)

### ADR-001: [Decision Title]

- **Status:** Proposed / Accepted / Deprecated
- **Context:** What situation or constraint forced this decision?
- **Decision:** What we chose and why.
- **Consequences:** What becomes easier, what becomes harder, what changes.
- **Alternatives Considered:** [Option A — rejected because X], [Option B — rejected because Y]

_Add more ADRs as needed._

## 5. API Contracts (if applicable)

```
POST /api/v1/resource
Request:  { field: string, ... }
Response: { id: string, ... }
Errors:   400 Bad Request, 401 Unauthorized, 500 Internal Server Error
```

## 6. Database Schema Changes (if applicable)

```sql
-- New table / migration description
CREATE TABLE ...
```

## 7. Security Considerations

- **Auth model:** [JWT / API key / session]
- **Data sensitivity:** [PII? encryption at rest?]
- **Threat vectors:** [injection points, SSRF risks, etc.]
- **Rate limiting:** [per-user? per-IP?]

## 8. Open Questions

| Question | Owner | Due |
|----------|-------|-----|
| [Question requiring resolution] | [agent/person] | YYYY-MM-DD |

## 9. Approval

- [ ] Architecture reviewed
- [ ] All ADRs accepted
- [ ] Security considerations addressed
- [ ] **APPROVED for Stories phase** — Date: _____ Approver: _____
