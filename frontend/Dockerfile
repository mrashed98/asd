FROM node:20-alpine

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

# Install system deps needed by node modules
RUN apk add --no-cache libc6-compat

# Install dependencies (include devDependencies for build)
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source
COPY . .

# Build Next.js app (needs devDependencies like typescript)
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

EXPOSE 3000

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "run", "start"]

