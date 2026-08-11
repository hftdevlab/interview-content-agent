.DEFAULT_GOAL := help

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
BUILD_DIR ?= build/practice
SANITIZER_BUILD_DIR ?= build/practice-ubsan
VERSION ?= 0.1.0

.PHONY: help lint validate test catalogs diagrams guides pdfs pdf-preview pdf-validate practice-configure practice-build practice-test practice-starter-check practice-sanitize docker-test release all ci clean

help: ## Show available developer commands
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

lint: ## Run dependency-free Markdown integrity checks
	$(PYTHON) -m tools.lint_markdown

validate: ## Validate schemas, taxonomy, content, references, and practice links
	$(PYTHON) -m tools.validate

test: ## Run deterministic Python tooling tests
	$(PYTHON) -m unittest discover -s tests -v

catalogs: ## Generate all metadata-driven question catalogs
	$(PYTHON) -m tools.generate_catalog

diagrams: ## Render Mermaid sources into generated SVG files
	$(PYTHON) -m tools.render_diagrams

guides: catalogs ## Build review-only combined Markdown guide previews
	$(PYTHON) -m tools.build_guides

pdfs: diagrams validate ## Build approved-only PDF guides under dist/
	$(PYTHON) -m tools.build_pdfs

pdf-preview: diagrams validate ## Build internal PDFs including review-stage content
	$(PYTHON) -m tools.build_pdfs --review-preview
	$(PYTHON) -m tools.validate_pdfs --review-preview

pdf-validate: pdfs ## Validate approved-only PDF structure and publication filtering
	$(PYTHON) -m tools.validate_pdfs

practice-configure: ## Configure the C++20 practice build
	cmake -S practice -B $(BUILD_DIR)

practice-build: practice-configure ## Compile starter and reference practice targets
	cmake --build $(BUILD_DIR)

practice-test: practice-build ## Run solution and starter-negative tests
	ctest --test-dir $(BUILD_DIR) --output-on-failure

practice-starter-check: practice-build ## Confirm unchanged starters fail behavioral tests
	ctest --test-dir $(BUILD_DIR) -L starter-negative --output-on-failure

practice-sanitize: ## Run solution tests with UndefinedBehaviorSanitizer
	cmake -S practice -B $(SANITIZER_BUILD_DIR) -DPRACTICE_ENABLE_UBSAN=ON
	cmake --build $(SANITIZER_BUILD_DIR)
	ctest --test-dir $(SANITIZER_BUILD_DIR) -L solution --output-on-failure --timeout 60

docker-test: ## Build and run the complete gate in Docker
	docker compose build
	docker compose run --rm content-factory

release: ## Build and package a versioned approved-content release
	$(PYTHON) -m tools.release --version $(VERSION)

all: test catalogs guides pdf-validate practice-test ## Run the complete deterministic source build

ci: lint all pdf-preview ## Run every pull-request validation and preview build

clean: ## Remove the local C++ build directory
	cmake -E remove_directory build
