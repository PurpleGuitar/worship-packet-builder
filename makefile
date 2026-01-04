# All .py files in non-dot subdirectories (exclude virtualenv, build/dist, hidden dirs)
PY_SOURCES := $(shell find . -type f -name '*.py' -not -path './.*' -not -path './.venv/*' -not -path './build/*' -not -path './dist/*')

#
# Run app
#

.PHONY: run
run: .venv
	. .venv/bin/activate && python3 main.py --trace

#
# Virtual environment management
#

.venv: requirements.txt
	# Create virtual environment
	python3 -m venv .venv
	# Install/update dependencies from requirements.txt
	. .venv/bin/activate; python3 -m pip install -r requirements.txt
	# Update modified date of .venv so that make knows it's been updated
	touch .venv

#
# Linting
#

.PHONY: mypy
mypy: .venv
	. .venv/bin/activate && python3 -m mypy --strict $(PY_SOURCES)

.PHONY: pylint
pylint: .venv
	. .venv/bin/activate && python3 -m pylint --jobs 4 --output-format=colorized $(PY_SOURCES)

.PHONY: lint
lint: .venv mypy pylint

#
# Testing
#

.PHONY: test
test: .venv
	. .venv/bin/activate \
	&& python3 -m coverage run --branch -m unittest discover -p "test*.py" \
	&& python3 -m coverage report \
	&& python3 -m coverage html

#
# Watch directories for changes
#

.PHONY: run-watch
run-watch:
	while inotifywait -e close_write,moved_to,create $(PY_SOURCES); do \
		clear; \
		sleep 1; \
		$(MAKE) run; \
	done

.PHONY: lint-watch
lint-watch:
	while inotifywait -e close_write,moved_to,create $(PY_SOURCES); do \
		clear; \
		sleep 1; \
		$(MAKE) lint; \
	done

.PHONY: test-watch
test-watch:
	while inotifywait -e close_write,moved_to,create $(PY_SOURCES); do \
		clear; \
		sleep 1; \
		$(MAKE) test; \
	done

.PHONY: lint-test-watch
lint-test-watch:
	while inotifywait -e close_write,moved_to,create $(PY_SOURCES); do \
		clear; \
		sleep 1; \
		$(MAKE) lint && $(MAKE) test; \
	done

#
# Create distributable package
#

.PHONY: dist
dist: .venv
	. .venv/bin/activate \
	&& pyinstaller --noconfirm --onefile main.py

#
# Editing and Formatting
#

.PHONY: edit
edit:
	${EDITOR} readme.md main.py $(PY_SOURCES) makefile requirements.txt .gitignore

.PHONY: format
format: .venv
	. .venv/bin/activate && python -m black $(PY_SOURCES)
	pandoc readme.md --from markdown --to gfm+smart --output readme.md

#
# Cleanup
#

.PHONY: clean
clean:
	rm -rf .mypy_cache
	rm -rf .venv
	rm -rf __pycache__
	rm -rf test/__pycache__
	rm -rf htmlcov
	rm -f .coverage
	rm -rf build
	rm -rf dist

# 
# Docker 
# 

# You can set a sensible default for DOCKER_IMAGE by sourcing env.sh.

.PHONY: docker-run
docker-run: docker-build
	test -n "$(DOCKER_IMAGE)" || (echo "DOCKER_IMAGE is not set" && exit 1)
	docker run --rm -it $(DOCKER_IMAGE) make run

.PHONY: docker-test
docker-test: docker-build
	test -n "$(DOCKER_IMAGE)" || (echo "DOCKER_IMAGE is not set" && exit 1)
	docker run --rm -it $(DOCKER_IMAGE) make test

.PHONY: docker-lint
docker-lint: docker-build
	test -n "$(DOCKER_IMAGE)" || (echo "DOCKER_IMAGE is not set" && exit 1)
	docker run --rm -it $(DOCKER_IMAGE) make lint

.PHONY: docker-clean
docker-clean:
	test -n "$(DOCKER_IMAGE)" || (echo "DOCKER_IMAGE is not set" && exit 1)
	docker image rm $(DOCKER_IMAGE) || true
	rm .docker-built || true

.PHONY: docker-build
docker-build: .docker-built

.docker-built: Dockerfile makefile requirements.txt $(PY_SOURCES)
	# Build the Docker image
	test -n "$(DOCKER_IMAGE)" || (echo "DOCKER_IMAGE is not set" && exit 1)
	docker build -t $(DOCKER_IMAGE) .
	touch .docker-built
