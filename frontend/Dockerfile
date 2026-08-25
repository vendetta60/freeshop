# syntax=docker/dockerfile:1
# =============================================================================
#  FreeShop web - BUILD ONLY.
#
#  The output of this stage is copied into the Caddy image by
#  docker-compose.yml. No Node process runs in production; the frontend has
#  zero runtime (plan.md 12.3).
# =============================================================================

FROM node:22-alpine AS build

WORKDIR /app

# VITE_* values are baked into the bundle at build time, so they must be
# present here rather than at container start.
ARG VITE_API_URL=/api/v1
ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_DEFAULT_LANG=az
ARG VITE_AUTH_PHONE_ENABLED=true
ENV VITE_API_URL=$VITE_API_URL \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID \
    VITE_DEFAULT_LANG=$VITE_DEFAULT_LANG \
    VITE_AUTH_PHONE_ENABLED=$VITE_AUTH_PHONE_ENABLED

# Copy manifests first so `npm ci` is cached until dependencies actually change.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# The static bundle, ready to be copied out.
FROM scratch AS dist
COPY --from=build /app/dist /dist
