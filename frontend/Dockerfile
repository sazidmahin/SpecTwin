# syntax=docker/dockerfile:1
FROM node:22-alpine AS build

WORKDIR /app

# API origin the browser uses to reach the backend (published on the host).
ARG VITE_API_ORIGIN=http://localhost:8000
ARG VITE_API_PREFIX=/api/v1
ENV VITE_API_ORIGIN=$VITE_API_ORIGIN \
    VITE_API_PREFIX=$VITE_API_PREFIX

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .
RUN yarn build

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

# Enable nginx logs to stdout/stderr (visible in docker compose logs)
RUN ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

# Run nginx in foreground (default, but explicit for clarity)
CMD ["nginx", "-g", "daemon off;"]
