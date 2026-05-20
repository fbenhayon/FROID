FROM node:20-alpine AS build
WORKDIR /app
COPY packages/froid-dashboard/package.json packages/froid-dashboard/package-lock.json ./
RUN npm ci
COPY packages/froid-dashboard/ .
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY packages/froid-dashboard/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80 443
