# Future Plans

## Transactional Email with Domain Verification

Currently, email sending is best-effort — failures are logged but non-fatal. To enable real email delivery (verification emails, password resets), a verified sender domain is required by Resend.

### What needs to happen

Get a custom domain and add Resend's DNS records (SPF, DKIM, DMARC) to it. Then set `RESEND_API_KEY` and `RESEND_FROM_EMAIL` in `.env.prod`.

### Options (in order of preference)

**Option A — Buy a domain via Cloudflare Registrar (recommended)**
- Already have a Cloudflare account for R2 storage
- Cheapest option (at-cost, no markup, ~$8–12/yr for `.com`)
- Add Resend's DNS records directly in Cloudflare dashboard
- Fast, everything in one place

**Option B — Use DigitalOcean DNS with any registrar**
- Register a domain anywhere (Namecheap, Google Domains, etc.)
- Point nameservers to `ns1/ns2/ns3.digitalocean.com`
- Add Resend's TXT records under Networking → Domains in the DO console

### Once domain is set up

1. In Resend dashboard → **Domains** → **Add Domain** → follow DNS instructions
2. Update `.env.prod` on the server:
   ```
   RESEND_FROM_EMAIL=noreply@yourdomain.com
   ```
3. Make `_send_email` in `src/core/email.py` raise on failure again (remove the silent-fail comment)
4. Redeploy
