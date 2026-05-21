FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ARG PUBLIC_API_URL=https://finance.bp0.work
ARG PUBLIC_SSE_URL=https://finance.bp0.work/events/stream
ENV PUBLIC_API_URL=${PUBLIC_API_URL} PUBLIC_SSE_URL=${PUBLIC_SSE_URL}
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
EXPOSE 3000
CMD ["node", "build"]
