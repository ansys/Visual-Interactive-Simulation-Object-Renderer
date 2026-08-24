FRONTEND_DIR ?= src/ansys/visor/visor-client
FRONTEND_BUILD_DIR ?= $(FRONTEND_DIR)/dist
BACKEND_STATIC_DIR ?= src/ansys/visor/viewer/client_bundle
WASM_OUT_DIR ?= $(BACKEND_STATIC_DIR)/wasm

.PHONY: clean clean-all _clean_python _clean_frontend _clean_static

_clean_python:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	rm -rf build/ dist/ *.egg-info .pytest_cache coverage-html

_clean_frontend:
	rm -rf $(FRONTEND_BUILD_DIR) $(FRONTEND_DIR)/build $(FRONTEND_DIR)/.vite $(FRONTEND_DIR)/.cache $(FRONTEND_DIR)/.parcel-cache

_clean_static:
	rm -rf $(WASM_OUT_DIR) $(BACKEND_STATIC_DIR)/assets $(BACKEND_STATIC_DIR)/manifest.* $(BACKEND_STATIC_DIR)/_temp tmp temp

clean:
	@$(MAKE) -s _clean_python _clean_frontend _clean_static

clean-all: clean
	@rm -rf $(FRONTEND_DIR)/node_modules
