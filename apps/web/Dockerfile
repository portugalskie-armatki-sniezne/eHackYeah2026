FROM node:24-alpine AS build
COPY --from=oven/bun:1.4.2-alpine /usr/local/bin/bun /usr/local/bin/bun
WORKDIR /app

# the backend URL is injected at build time because Vite inlines VITE_* values into the bundle
# in CD: docker build --build-arg VITE_API_URL=https://api.example.com/ ...
ARG VITE_API_URL=http://localhost:8000/
ENV VITE_API_URL=$VITE_API_URL

# the build context is the repository root because bun.lock covers all workspaces
COPY package.json bun.lock ./
COPY apps/web/package.json apps/web/
RUN bun install --frozen-lockfile
COPY apps/web apps/web
RUN bun run --cwd apps/web build


FROM nginx:alpine
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

RUN echo 'server { listen 80; location / { root /usr/share/nginx/html; index index.html; try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
