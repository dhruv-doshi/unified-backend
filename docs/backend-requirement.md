# Backend Requirements — Shoot Right

All endpoints are prefixed `/api/v1`. Bearer token authentication via `Authorization: Bearer <accessToken>` unless marked **No Auth**.

---

## Authentication Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Register with email + password. Body: `{ name, email, password }` |
| POST | `/auth/login` | No | Login → returns `{ user, accessToken }`. Body: `{ email, password }` |
| POST | `/auth/forgot-password` | No | Send password reset email. Body: `{ email }` |
| POST | `/auth/reset-password` | No | Reset password with token. Body: `{ token, password }` |
| POST | `/auth/verify-email` | No | Verify email address. Body: `{ token }` |
| POST | `/auth/oauth-callback` | No | Exchange Google `id_token` for backend `accessToken`. Body: `{ idToken, provider: "google" }` |

### Auth Response Shape
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "accessToken": "jwt-token-here",
    "user": {
      "id": "uuid",
      "name": "Alex Johnson",
      "email": "alex@example.com",
      "image": "https://..."
    }
  }
}
```

---

## Analysis Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/analysis/upload` | Yes | Upload image for analysis. Returns `analysisId` + `status` |
| GET | `/analysis/:id` | Yes | Get full analysis data |
| POST | `/analysis/:id/improvement-shot` | Yes | Generate or retrieve improved image |

### POST `/analysis/upload`
- Content-Type: `multipart/form-data`
- Fields:
  - `image` (File) — the image file
  - `histogram` (JSON string, optional) — pre-computed histogram from frontend canvas
- Response:
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
- Status values: `"processing"` | `"completed"` | `"failed"`
- Rate limit: 10 uploads per hour per user

### GET `/analysis/:id`
Full analysis response:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "imageUrl": "https://cdn.example.com/images/uuid.jpg",
    "thumbnailUrl": "https://cdn.example.com/thumbs/uuid.jpg",
    "filename": "mountain.jpg",
    "uploadedAt": "2026-03-10T09:30:00Z",
    "status": "completed",
    "overallScore": 78,
    "summaryHeadline": "Strong Composition with Room for Improvement",
    "summaryText": "...",
    "metadata": {
      "make": "Sony", "model": "α7R V", "lens": "...",
      "focalLength": 35, "aperture": 8, "shutterSpeed": "1/250",
      "iso": 200, "exposureMode": "Aperture Priority", "whiteBalance": "Auto",
      "flash": "No Flash", "dateTaken": "2026-03-10T06:45:22Z",
      "width": 9504, "height": 6336, "fileSize": 24576000, "format": "JPEG",
      "gps": { "lat": 46.8523, "lng": -121.7603 }
    },
    "histogram": {
      "red": [/* 256 values, 0-255 */],
      "green": [/* 256 values */],
      "blue": [/* 256 values */],
      "luminance": [/* 256 values */]
    },
    "composition": {
      "score": 84,
      "strengths": ["Horizon at upper third", "Strong leading lines"],
      "weaknesses": ["Slight horizon tilt"],
      "details": "..."
    },
    "technical": {
      "score": 71,
      "sharpness": "good",
      "exposure": "slightly-over",
      "noise": "minimal",
      "strengths": ["Excellent depth of field", "Low noise"],
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
    "clickingTips": ["Tip 1", "Tip 2", "..."],
    "editingTips": ["Tip 1", "Tip 2", "..."],
    "improvementShot": null
  }
}
```

### POST `/analysis/:id/improvement-shot`
- Idempotent — returns existing result if already generated
- Rate limit: 3 per day per user
- Response:
```json
{
  "success": true,
  "data": {
    "url": "https://cdn.example.com/improved/uuid.jpg",
    "explanation": "Applied the following improvements: ...",
    "generatedAt": "2026-03-10T10:00:00Z"
  }
}
```

---

## User Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/user/images` | Yes | Paginated gallery of user's uploads |
| DELETE | `/user/images/:id` | Yes | Delete image + analysis |
| GET | `/user/profile` | Yes | Get user profile |
| PATCH | `/user/profile` | Yes | Update name/avatar |

### GET `/user/images`
Query params: `page` (default 1), `limit` (default 20)
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "url": "https://cdn.example.com/images/uuid.jpg",
      "thumbnailUrl": "https://cdn.example.com/thumbs/uuid.jpg",
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

---

## General Notes

### Error Response Shape
```json
{
  "success": false,
  "message": "Human-readable error message",
  "code": "MACHINE_READABLE_CODE",
  "statusCode": 400
}
```

### Rate Limits
- Upload: 10 per hour per user
- Improvement shot generation: 3 per day per user

### CDN & Media
- Images served via CDN with signed URLs (24h expiry) OR public URLs
- Supported upload formats: JPEG, PNG, WebP, HEIC
- Max upload size: 20 MB

### LLM Pipeline
The backend handles all LLM calls. The frontend sends the image + optional client-extracted histogram. The analysis pipeline runs asynchronously — `status` may be `"processing"` initially. Frontend should poll `GET /analysis/:id` until `status === "completed"`.

### JWT
- Tokens should include: `{ sub: userId, email, name, iat, exp }`
- Expiry: 7 days recommended (with refresh token support optional)
