# API Versioning Strategies

## 🎯 When to Use

- Breaking changes to existing APIs
- Deprecating old endpoints
- Multiple API versions coexisting

## 📊 Strategy Comparison

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| **URL Path** (`/v1/`, `/v2/`) | Clear, cacheable | URL pollution | Public APIs |
| **Header** (`API-Version: 2`) | Clean URLs | Hidden, harder to test | Internal |
| **Query** (`?version=2`) | Easy | Cache issues | Temporary |
| **Content Negotiation** | RESTful | Complex | Standards-based |

## 🔄 Deprecation Process

1. Announce deprecation in response headers
2. Document migration path
3. Set sunset date (min 6 months)
4. Monitor usage
5. Remove after zero usage

## 📝 Header Format

```
Deprecation: true
Sunset: Sat, 31 Dec 2026 23:59:59 GMT
Link: <https://api.example.com/v2/users>; rel="successor-version"
```