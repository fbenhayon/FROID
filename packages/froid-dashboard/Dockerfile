FROM node:20-alpine AS build
WORKDIR /app
COPY packages/froid-dashboard/package.json packages/froid-dashboard/package-lock.json ./
RUN npm ci
COPY packages/froid-dashboard/ .
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
RUN apk add --no-cache openssl && \
    mkdir -p /etc/nginx/ssl && \
    openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
      -keyout /etc/nginx/ssl/key.pem \
      -out /etc/nginx/ssl/cert.pem \
      -subj "/C=BR/O=FROID/CN=froid" \
      -addext "subjectAltName=IP:204.168.229.32,IP:127.0.0.1"
COPY --from=build /app/dist /usr/share/nginx/html
COPY packages/froid-dashboard/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80 443
