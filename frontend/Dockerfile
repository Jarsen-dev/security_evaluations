# ===========================================================================
# Frontend Next.js — imagen multi-stage
#   target `dev`  -> next dev con recarga en caliente
#   target `prod` -> build standalone, usuario sin privilegios (default)
# ===========================================================================

FROM node:20-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

# --- Dependencias ----------------------------------------------------------
FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci

# --- Desarrollo ------------------------------------------------------------
FROM base AS dev
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# --- Build de producción ---------------------------------------------------
FROM base AS builder
# Next.js incrusta las NEXT_PUBLIC_* en el bundle en tiempo de build:
# si esta variable falta aquí, las ligas y los QR salen vacíos.
ARG NEXT_PUBLIC_BASE_URL
ENV NEXT_PUBLIC_BASE_URL=${NEXT_PUBLIC_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- Producción ------------------------------------------------------------
FROM base AS prod
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
# La salida standalone ya trae el servidor y solo las dependencias usadas.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
