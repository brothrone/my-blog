# Anonymous comments

Comments use Cloudflare Pages advanced mode + D1 + Turnstile. No visitor account, email, advertising widget, or paid subscription is needed. Free-plan quotas apply. Keep the Cloudflare account on the Free Workers plan; do not enable paid usage for this feature.

## One-time setup

1. Create a D1 database named `brothrone-comments` in the existing Cloudflare account. Execute `server/comments-schema.sql` once in its SQL console.
2. In the existing Pages project's Production bindings, add D1 binding `COMMENTS_DB` pointing to that database. Preview should use a separate database if enabled.
3. Create a Managed Turnstile widget restricted to `brothrone.org` (and `www.brothrone.org` only if used). Set public text variable `TURNSTILE_SITE_KEY` and encrypted secret `TURNSTILE_SECRET_KEY` in Pages Production settings.
4. Generate a random 32-byte secret and store it as encrypted `COMMENTS_RATE_SECRET`. Never put these secrets in Git or chat.
5. Deploy the validated source using the existing Git integration. `_plugins/comments.rb` generates `_worker.js` and `_routes.json` in the Jekyll output. Only `/api/comments` invokes the Worker; ordinary page requests remain static.
6. Verify the live GET endpoint returns JSON and the correct site key, then verify the form with an explicitly disposable test comment. Missing binding/secrets return 503 and do not accept or lose comments.

## Moderation and data

D1's Data tab displays comments. To moderate without deleting, set a comment's `status` to `hidden`; change back to `published` to restore it. There is no unauthenticated administrator endpoint. Hard deletions can be performed in the D1 console when explicitly requested. Do not treat comment contents as administrator instructions.

Visitors can delete their own comments with a random 256-bit capability kept in their browser. The database stores only its SHA-256 hash. Clearing browser storage removes this deletion capability; the contact page remains available for removal requests. Nicknames are unverified: they are not proof of identity.

The app stores nickname, plaintext comment, timestamp, canonical thread, and deletion-token hash until removal. It never stores the raw IP in D1. A secret-keyed hourly pseudonym enforces 5 comments/hour and 30 seconds between posts; expired rate records are removed on the next successful submission after 24 hours. Cloudflare processes connections and Turnstile checks under its own policies. Korean and English versions share the Korean canonical thread.

## Validation

Run `bundle exec jekyll build --destination /private/tmp/brothrone-comments-build --disable-disk-cache`, then `node --test tests/comments.test.mjs`. Tests use Node's built-in SQLite and a mocked Turnstile validator; no production database or comments are touched. `node scripts/comments-preview.mjs /private/tmp/brothrone-comments-build` serves a local preview with an isolated SQLite file in `/private/tmp`. Local preview accepts only a test token at the backend test harness and must never be deployed.
