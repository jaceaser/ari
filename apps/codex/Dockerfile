FROM node:20-alpine AS base

# --- Dependencies stage ---
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

# --- Build stage ---
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# --- Production stage ---
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy standalone output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Copy course content — read at runtime by content-loader.ts via process.cwd()/course-guides/
COPY --from=builder /app/course-guides ./course-guides

RUN mkdir -p .next/cache \
    && chown -R nextjs:nodejs .next/cache \
    && chown -R nextjs:nodejs ./course-guides

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
