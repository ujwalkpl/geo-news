FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# VITE_* vars baked into JS bundle at build time — passed as build args
ARG VITE_API_URL=https://geonews-api-4loazyhcxa-uc.a.run.app
ARG VITE_WS_URL=wss://geonews-websocket-4loazyhcxa-uc.a.run.app/ws
ARG VITE_MAPBOX_TOKEN
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
