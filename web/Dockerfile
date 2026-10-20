# Next.js UI. Build context must be the hr-assistant repo root.
# cn@0.5 (shadcn helper) requires Node >= 22
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY web/package.json web/yarn.lock ./
RUN yarn install --frozen-lockfile

FROM node:22-bookworm-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY web/ ./
COPY data /data
ENV DATA_DIR=/data
ENV NEXT_TELEMETRY_DISABLED=1
# API_URL is baked into rewrites at build time for SSR; runtime still needs it for rewrites on start.
ARG API_URL=http://localhost:8000
ENV API_URL=$API_URL
RUN yarn build

FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV DATA_DIR=/data
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /data /data
USER node
EXPOSE 3000
CMD ["node", "server.js"]
