# Frontend Integration Guide — Shoot Right Backend

This document describes everything the frontend needs to know to integrate with this backend.
All endpoints are under `/api/v1`.

---

## Base URL

| Environment | Base URL |
|-------------|----------|
| Local (direct) | `http://localhost:8000/api/v1` |
| Local (via Nginx) | `http://localhost/api/v1` |
| Production | `https://your-domain.com/api/v1` |

---

## Authentication

All protected endpoints require:
```
Authorization: Bearer <accessToken>
```

- Token is a **JWT** containing `{ sub, email, name, iat, exp }`
- **Expiry:** 7 days (10080 minutes)
- **No refresh token** — re-login when expired
- Store the token in `localStorage` or `sessionStorage`

---

## Response Envelope

### Success
```json
{
  "success": true,
  "message": "Human readable",
  "data": { ... }
}
```

### Error
```json
{
  "success": false,
  "message": "Human readable error",
  "code": "MACHINE_READABLE_CODE",
  "statusCode": 400
}
```

### Error Codes to Handle

| Code | HTTP Status | When |
|------|-------------|------|
| `EMAIL_EXISTS` | 409 | Register with duplicate email |
| `INVALID_CREDENTIALS` | 401 | Wrong email/password |
| `EMAIL_NOT_VERIFIED` | 403 | Login before verifying email |
| `TOKEN_EXPIRED` | 401 | JWT or verification/reset token expired |
| `TOKEN_INVALID` | 401 | Bad JWT or bad verification/reset token |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many uploads or improvement shots |
| `NOT_FOUND` | 404 | Analysis/user not found |
| `FORBIDDEN` | 403 | Accessing another user's resource |
| `VALIDATION_ERROR` | 422 | Request body fails validation |
| `FILE_TOO_LARGE` | 413 | Image > 20MB |
| `UNSUPPORTED_FORMAT` | 415 | Not JPEG/PNG/WebP/HEIC |
| `ANALYSIS_NOT_COMPLETE` | 400 | Improvement shot on non-completed analysis |

---

## Auth Endpoints

### POST `/auth/register`
**No auth required**

Request:
```json
{
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "password": "MinimumEightChars"
}
```

Response `201`:
```json
{
  "success": true,
  "data": {
    "accessToken": "eyJ...",
    "user": {
      "id": "uuid",
      "name": "Alice Johnson",
      "email": "alice@example.com",
      "image": null
    }
  }
}
```

**Note:** User is NOT verified yet. A verification email is sent. The returned token works for API calls but the user will hit `EMAIL_NOT_VERIFIED` on login until they verify.

**Recommendation:** After registration, show "Check your email to verify your account" and redirect to login — do NOT auto-login using the registration token.

---

### POST `/auth/login`
**No auth required**

Request:
```json
{ "email": "alice@example.com", "password": "MinimumEightChars" }
```

Response `200` — same shape as register.

**Possible errors:** `INVALID_CREDENTIALS` (401), `EMAIL_NOT_VERIFIED` (403)

When you get `EMAIL_NOT_VERIFIED`, show a message: "Please verify your email. Check your inbox." Optionally add a "Resend verification email" button (not yet implemented — can be added).

---

### POST `/auth/verify-email`
**No auth required**

The verification link in the email should point to your frontend, e.g.:
`https://yourapp.com/verify-email?token=<token>`

Your frontend page extracts the token from the URL and calls:
```json
{ "token": "<token-from-url>" }
```

Response `200`:
```json
{ "success": true, "data": null, "message": "Email verified successfully" }
```

After success, redirect to login page.

**Possible errors:** `TOKEN_INVALID` (401), `TOKEN_EXPIRED` (401)

---

### POST `/auth/forgot-password`
**No auth required**

```json
{ "email": "alice@example.com" }
```

Always returns `200` regardless of whether the email exists (prevents enumeration).

---

### POST `/auth/reset-password`
**No auth required**

The reset link in email points to: `https://yourapp.com/reset-password?token=<token>`

```json
{ "token": "<token-from-url>", "password": "NewPassword123" }
```

Response `200` on success. Redirect to login after.

---

### POST `/auth/oauth-callback`
**No auth required**

For Google Sign In. After the Google OAuth flow completes on the frontend, send the `id_token`:
```json
{ "idToken": "<google-id-token>", "provider": "google" }
```

Response `200` — same shape as register/login. The user is automatically verified.

---

## Analysis Endpoints

All require `Authorization: Bearer <token>`.

### POST `/analysis/upload`
**Content-Type: `multipart/form-data`**

Fields:
- `image` (File, required) — JPEG, PNG, WebP, or HEIC; max 20MB
- `histogram` (string, optional) — JSON string of pre-computed histogram: `{"red":[...256 values...],"green":[...],"blue":[...],"luminance":[...]}`

Response `202`:
```json
{
  "success": true,
  "data": {
    "analysisId": "uuid",
    "status": "processing",
    "message": "Upload received. Analysis in progress."
  }
}
```

**Rate limit:** 10 per hour. Returns `RATE_LIMIT_EXCEEDED` (429) when exceeded.

**Flow:** After getting `analysisId`, poll `GET /analysis/:id` until `status === "completed"`.

---

### GET `/analysis/:id`
Poll this endpoint until `status` is `"completed"` or `"failed"`.

Recommended polling interval: 3–5 seconds, max 60 attempts.

Response `200`:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "imageUrl": "https://cdn.example.com/shoot_right/originals/...",
    "thumbnailUrl": "https://cdn.example.com/shoot_right/thumbnails/...",
    "filename": "mountain.jpg",
    "uploadedAt": "2026-03-10T09:30:00Z",
    "status": "completed",
    "overallScore": 78,
    "summaryHeadline": "Strong Composition with Room for Improvement",
    "summaryText": "...",
    "metadata": {
      "make": "Sony",
      "model": "α7R V",
      "lens": "FE 35mm F1.4 GM",
      "focalLength": "35",
      "aperture": "8",
      "shutterSpeed": "1/250",
      "iso": "200",
      "exposureMode": "1",
      "whiteBalance": "0",
      "flash": "Flash did not fire",
      "dateTaken": "2026:03:10 06:45:22",
      "width": 9504,
      "height": 6336,
      "format": "JPEG",
      "fileSize": 24576000,
      "gps": { "lat": 46.8523, "lng": -121.7603 }
    },
    "histogram": {
      "red": [/* 256 integer values */],
      "green": [/* 256 integer values */],
      "blue": [/* 256 integer values */],
      "luminance": [/* 256 integer values */]
    },
    "composition": {
      "score": 84,
      "strengths": ["Horizon at upper third", "Strong leading lines"],
      "weaknesses": ["Slight horizon tilt"],
      "details": "The composition demonstrates..."
    },
    "technical": {
      "score": 71,
      "sharpness": "good",
      "exposure": "slightly-over",
      "noise": "minimal",
      "strengths": ["Excellent depth of field"],
      "weaknesses": ["Highlight clipping in clouds"],
      "details": "..."
    },
    "colorAesthetic": {
      "score": 82,
      "dominantColors": [
        { "hex": "#E8A87C", "name": "Warm Amber", "percentage": 28 }
      ],
      "colorHarmony": "Complementary",
      "mood": "Serene, Expansive",
      "strengths": ["Natural warm-cool harmony"],
      "weaknesses": ["Slight yellow cast in shadows"],
      "details": "..."
    },
    "clickingTips": ["Tip 1", "Tip 2"],
    "editingTips": ["Tip 1", "Tip 2"],
    "improvementShot": null
  }
}
```

**Status values:** `"processing"` | `"completed"` | `"failed"`

When `status === "failed"`, show an error state. Do not continue polling.

**Nullable fields while `status === "processing"`:** `overallScore`, `summaryHeadline`, `summaryText`, `metadata`, `histogram`, `composition`, `technical`, `colorAesthetic`, `clickingTips`, `editingTips`, `improvementShot`

---

### POST `/analysis/:id/improvement-shot`
Generate (or retrieve) an improvement prescription for a completed analysis.

**Rate limit:** 3 per day. Returns `RATE_LIMIT_EXCEEDED` (429) when exceeded.

**Response `202`** (newly generated) or **`200`** (already exists — idempotent):
```json
{
  "success": true,
  "data": {
    "url": null,
    "explanation": "To improve this shot, adjust your aperture to f/5.6 for better subject separation...",
    "generatedAt": "2026-03-10T10:00:00Z"
  }
}
```

**Note:** `url` is `null` in MVP. The improvement is text-only (`explanation`). Image generation is not wired up yet.

---

## User Endpoints

All require `Authorization: Bearer <token>`.

### GET `/user/profile`
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Alice Johnson",
    "email": "alice@example.com",
    "image": "https://cdn.example.com/avatars/..."
  }
}
```

---

### PATCH `/user/profile`
**Content-Type: `multipart/form-data`** (not JSON!)

Fields (all optional):
- `name` (string) — new display name
- `avatar` (File) — new profile image

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Alice Updated",
    "email": "alice@example.com",
    "image": "https://cdn.example.com/avatars/..."
  }
}
```

---

### GET `/user/images?page=1&limit=20`
Paginated gallery of the user's uploads.

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "url": "https://cdn.example.com/...",
      "thumbnailUrl": "https://cdn.example.com/...",
      "uploadedAt": "2026-03-10T09:30:00Z",
      "filename": "mountain.jpg",
      "overallScore": 78,
      "summaryHeadline": "Strong Composition",
      "status": "completed"
    }
  ],
  "total": 42,
  "page": 1,
  "limit": 20,
  "hasNext": true
}
```

**Note:** This response has pagination fields at the top level (not nested in `data`), alongside `success: true`.

---

### DELETE `/user/images/:id`
Deletes the analysis and removes images from storage.

Response `200`:
```json
{ "success": true, "data": null, "message": "Image deleted successfully" }
```

**Errors:** `NOT_FOUND` (404), `FORBIDDEN` (403)

---

## Key Differences from Original Spec

### 1. All keys are camelCase
Both request bodies and responses use camelCase:
- `accessToken` (not `access_token`)
- `imageUrl` (not `image_url`)
- `colorAesthetic` (not `color_aesthetic`)
- `clickingTips` (not `clicking_tips`)
- `overallScore` (not `overall_score`)
- `idToken` (not `id_token` in oauth-callback)

### 2. PATCH /user/profile is multipart (not JSON)
Use `FormData` in JavaScript:
```javascript
const form = new FormData();
if (name) form.append('name', name);
if (avatarFile) form.append('avatar', avatarFile);
await fetch('/api/v1/user/profile', { method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: form });
```
Do NOT set `Content-Type` header manually — the browser sets it with the correct boundary.

### 3. Improvement shot status codes
- `202` = newly generated (may take a few seconds, consider a loading state)
- `200` = already exists (show immediately)
Both return the same data shape.

### 4. Gallery response structure
The gallery endpoint (`GET /user/images`) has pagination fields at top level, not nested:
```json
{ "success": true, "data": [...], "total": 42, "page": 1, "limit": 20, "hasNext": true }
```

### 5. `url` in improvement shot is always null (MVP)
`improvementShot.url` will be `null`. Only `explanation` and `generatedAt` are populated.

### 6. Register returns a token but user is unverified
After registration, a token IS returned, but the user cannot use `POST /auth/login` until they verify their email. Use the registration flow to show a "verify email" screen instead of auto-logging in.

### 7. Metadata fields are raw strings from EXIF
`focalLength`, `aperture`, `shutterSpeed`, `iso` come back as strings (e.g. `"35"`, `"8"`, `"1/250"`). Parse them on the frontend if you need numeric values.

---

## Frontend Environment Variables Needed

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_GOOGLE_CLIENT_ID=<your-google-client-id>
```

---

## Polling Pattern (TypeScript example)

```typescript
async function pollAnalysis(analysisId: string, token: string) {
  const MAX_ATTEMPTS = 60;
  const INTERVAL_MS = 3000;

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const res = await fetch(`/api/v1/analysis/${analysisId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const { data } = await res.json();

    if (data.status === 'completed') return data;
    if (data.status === 'failed') throw new Error('Analysis failed');

    await new Promise((resolve) => setTimeout(resolve, INTERVAL_MS));
  }
  throw new Error('Analysis timed out');
}
```

---

## File Upload Pattern (TypeScript example)

```typescript
async function uploadImage(file: File, token: string, histogram?: object) {
  const form = new FormData();
  form.append('image', file);
  if (histogram) form.append('histogram', JSON.stringify(histogram));

  const res = await fetch('/api/v1/analysis/upload', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    // DO NOT set Content-Type — browser handles multipart boundary automatically
  });

  if (res.status === 429) throw new Error('Rate limit exceeded. Try again in an hour.');
  if (!res.ok) throw new Error('Upload failed');

  const { data } = await res.json();
  return data.analysisId; // UUID string
}
```
