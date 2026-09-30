FROM golang:alpine AS builder

RUN apk add --no-cache git make

WORKDIR /app
COPY . .
RUN go mod tidy && \
    CGO_ENABLED=0 go build -ldflags "-s -w" -o /cfpctl .

FROM alpine:latest
COPY --from=builder /cfpctl /usr/local/bin/cfpctl
ENTRYPOINT ["cfpctl"]
