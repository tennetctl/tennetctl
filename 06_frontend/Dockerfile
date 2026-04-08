# syntax=docker/dockerfile:1.7
# tennetctl frontend — Next.js 15 (App Router) + Tailwind v4

# ---- deps ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install --no-audit --no-fund

# ---- build ----
FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- runtime ----
FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Non-root runtime user (uid 10002 — distinct from the backend so a
# compromise of one container does not match the other's filesystem owner).
RUN addgroup -S -g 10002 app && adduser -S -u 10002 -G app -s /sbin/nologin app

# Standalone output bundles only what's needed. Owned by the runtime user
# so the read-only filesystem in compose still permits node to read its own files.
COPY --from=build --chown=app:app /app/public ./public
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static

USER app:app

EXPOSE 3000

CMD ["node", "server.js"]
