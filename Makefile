BINARY   := cfpctl
MODULE   := github.com/cfpctl/cfpctl
VERSION  ?= dev
COMMIT   := $(shell git rev-parse --short HEAD 2>/dev/null || echo "none")
DATE     := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
LDFLAGS  := -s -w \
  -X $(MODULE)/cmd.version=$(VERSION) \
  -X $(MODULE)/cmd.commit=$(COMMIT) \
  -X $(MODULE)/cmd.date=$(DATE)

DOCKER_IMAGE := golang:alpine
DOCKER_RUN   := docker run --rm -v $(CURDIR):/app -w /app $(DOCKER_IMAGE)

.PHONY: build clean test lint deps docker-build docker-shell

# Build using local Go
build:
	go build -ldflags "$(LDFLAGS)" -o bin/$(BINARY) .

# Build inside Docker (no local Go needed)
docker-build:
	$(DOCKER_RUN) sh -c "go mod tidy && go build -ldflags '$(LDFLAGS)' -o bin/$(BINARY) ."

# Interactive shell in Docker for development
docker-shell:
	docker run -it --rm -v $(CURDIR):/app -w /app $(DOCKER_IMAGE) sh

deps:
	$(DOCKER_RUN) go mod tidy

test:
	$(DOCKER_RUN) go test ./...

lint:
	$(DOCKER_RUN) go vet ./...

clean:
	rm -rf bin/

# Cross-compile targets
build-all: docker-build-linux docker-build-darwin docker-build-windows

docker-build-linux:
	$(DOCKER_RUN) sh -c "GOOS=linux GOARCH=amd64 go build -ldflags '$(LDFLAGS)' -o bin/$(BINARY)-linux-amd64 ."

docker-build-darwin:
	$(DOCKER_RUN) sh -c "GOOS=darwin GOARCH=arm64 go build -ldflags '$(LDFLAGS)' -o bin/$(BINARY)-darwin-arm64 ."

docker-build-windows:
	$(DOCKER_RUN) sh -c "GOOS=windows GOARCH=amd64 go build -ldflags '$(LDFLAGS)' -o bin/$(BINARY)-windows-amd64.exe ."
