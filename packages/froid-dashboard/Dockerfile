FROM node:20-alpine AS build
WORKDIR /app
COPY packages/froid-dashboard/package.json ./
RUN npm install --legacy-peer-deps
RUN npm install --save-dev typescript
COPY packages/froid-dashboard/ .
ARG VITE_API_URL=http://204.168.229.32:8001
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY packages/froid-dashboard/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
