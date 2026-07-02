FROM node:20-alpine AS builder

WORKDIR /app

COPY apps/api/package*.json ./
RUN npm ci

COPY apps/api/ ./
COPY packages/shared /packages/shared

RUN npm run build

FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/package*.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist

EXPOSE 4000

CMD ["node", "dist/main.js"]
