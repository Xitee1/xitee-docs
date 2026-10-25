# Build stage
FROM python:3.14-alpine AS builder

WORKDIR /app

# Install git (required for git-revision-date-localized-plugin)
RUN apk add --no-cache git

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files (including .git for git-revision-date plugin)
COPY . .

# Build the static site
# Note: Ensure fetch-depth: 0 in CI for git history
RUN mkdocs build

# Production stage - use nginx alpine for minimal footprint
FROM nginx:alpine

# Copy built static files to nginx
COPY --from=builder /app/site /usr/share/nginx/html

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
