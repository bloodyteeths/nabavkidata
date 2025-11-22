.PHONY: help setup run-dev run-prod test migrate backup restore deploy logs clean

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

# Project paths
PROJECT_ROOT := $(shell pwd)
BACKEND_DIR := $(PROJECT_ROOT)/backend
FRONTEND_DIR := $(PROJECT_ROOT)/frontend
SCRIPTS_DIR := $(PROJECT_ROOT)/scripts

help: ## Show this help message
	@echo "$(GREEN)Nabavki Data - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

setup: ## Initial project setup
	@echo "$(GREEN)Running initial setup...$(NC)"
	@bash $(SCRIPTS_DIR)/setup.sh

setup-force: ## Force setup (reinstall dependencies)
	@echo "$(GREEN)Running forced setup...$(NC)"
	@bash $(SCRIPTS_DIR)/setup.sh --skip-seed

generate-env: ## Generate .env files with random secrets
	@echo "$(GREEN)Generating environment files...$(NC)"
	@bash $(SCRIPTS_DIR)/generate-env.sh

generate-env-prod: ## Generate production .env files
	@echo "$(YELLOW)Generating production environment files...$(NC)"
	@bash $(SCRIPTS_DIR)/generate-env.sh --environment production

run-dev: ## Run development servers (backend + frontend)
	@echo "$(GREEN)Starting development servers...$(NC)"
	@trap 'kill 0' EXIT; \
	(cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py runserver) & \
	(cd $(FRONTEND_DIR) && npm run dev)

run-backend: ## Run backend only
	@echo "$(GREEN)Starting backend server...$(NC)"
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py runserver

run-frontend: ## Run frontend only
	@echo "$(GREEN)Starting frontend server...$(NC)"
	@cd $(FRONTEND_DIR) && npm run dev

run-prod: ## Run production build
	@echo "$(GREEN)Starting production servers...$(NC)"
	@trap 'kill 0' EXIT; \
	(cd $(BACKEND_DIR) && source venv/bin/activate && gunicorn config.wsgi:application --bind 0.0.0.0:8000) & \
	(cd $(FRONTEND_DIR) && npm run start)

build-frontend: ## Build frontend for production
	@echo "$(GREEN)Building frontend...$(NC)"
	@cd $(FRONTEND_DIR) && npm run build

test: ## Run all tests
	@echo "$(GREEN)Running tests...$(NC)"
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py test
	@cd $(FRONTEND_DIR) && npm test

test-backend: ## Run backend tests only
	@echo "$(GREEN)Running backend tests...$(NC)"
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py test

test-frontend: ## Run frontend tests only
	@echo "$(GREEN)Running frontend tests...$(NC)"
	@cd $(FRONTEND_DIR) && npm test

migrate: ## Run database migrations
	@echo "$(GREEN)Running database migrations...$(NC)"
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py migrate

makemigrations: ## Create new migrations
	@echo "$(GREEN)Creating migrations...$(NC)"
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py makemigrations

seed-data: ## Seed database with sample data
	@echo "$(GREEN)Seeding database...$(NC)"
	@bash $(SCRIPTS_DIR)/seed-data.sh

scrape: ## Run tender scraper
	@echo "$(GREEN)Running scraper...$(NC)"
	@bash $(SCRIPTS_DIR)/run-scraper.sh

scrape-full: ## Run full scraper (not incremental)
	@echo "$(GREEN)Running full scraper...$(NC)"
	@bash $(SCRIPTS_DIR)/run-scraper.sh --full

backup: ## Create database and files backup
	@echo "$(GREEN)Creating backup...$(NC)"
	@bash $(SCRIPTS_DIR)/backup.sh

backup-s3: ## Create backup and upload to S3
	@echo "$(GREEN)Creating backup and uploading to S3...$(NC)"
	@bash $(SCRIPTS_DIR)/backup.sh --s3

restore: ## Restore from backup
	@echo "$(YELLOW)Restore from backup$(NC)"
	@read -p "Enter backup timestamp (e.g., 20250122_143000): " timestamp; \
	bash $(SCRIPTS_DIR)/restore.sh $$timestamp

restore-s3: ## Restore from S3 backup
	@echo "$(YELLOW)Restore from S3 backup$(NC)"
	@read -p "Enter backup timestamp (e.g., 20250122_143000): " timestamp; \
	bash $(SCRIPTS_DIR)/restore.sh $$timestamp --from-s3

health-check: ## Check system health
	@bash $(SCRIPTS_DIR)/health-check.sh --verbose

deploy: ## Deploy to production
	@echo "$(YELLOW)Deploying to production...$(NC)"
	@git pull origin main
	@cd $(BACKEND_DIR) && source venv/bin/activate && pip install -r requirements.txt
	@cd $(FRONTEND_DIR) && npm install
	@$(MAKE) migrate
	@$(MAKE) build-frontend
	@sudo systemctl restart nabavki-backend
	@sudo systemctl restart nabavki-frontend
	@echo "$(GREEN)Deployment completed!$(NC)"

logs: ## View application logs
	@echo "$(GREEN)Viewing logs...$(NC)"
	@tail -f $(PROJECT_ROOT)/logs/*.log

logs-backend: ## View backend logs
	@echo "$(GREEN)Viewing backend logs...$(NC)"
	@journalctl -u nabavki-backend -f

logs-frontend: ## View frontend logs
	@echo "$(GREEN)Viewing frontend logs...$(NC)"
	@journalctl -u nabavki-frontend -f

logs-scraper: ## View scraper logs
	@echo "$(GREEN)Viewing scraper logs...$(NC)"
	@tail -f $(PROJECT_ROOT)/logs/scraper_*.log

shell: ## Open Django shell
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py shell

dbshell: ## Open database shell
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py dbshell

createsuperuser: ## Create Django superuser
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py createsuperuser

lint: ## Run linters
	@echo "$(GREEN)Running linters...$(NC)"
	@cd $(BACKEND_DIR) && source venv/bin/activate && flake8 .
	@cd $(FRONTEND_DIR) && npm run lint

format: ## Format code
	@echo "$(GREEN)Formatting code...$(NC)"
	@cd $(BACKEND_DIR) && source venv/bin/activate && black .
	@cd $(FRONTEND_DIR) && npm run format

clean: ## Clean temporary files
	@echo "$(GREEN)Cleaning temporary files...$(NC)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@cd $(FRONTEND_DIR) && rm -rf .next node_modules/.cache
	@echo "$(GREEN)Cleanup completed!$(NC)"

clean-all: clean ## Clean all generated files including dependencies
	@echo "$(YELLOW)Cleaning all generated files...$(NC)"
	@cd $(BACKEND_DIR) && rm -rf venv
	@cd $(FRONTEND_DIR) && rm -rf node_modules .next
	@echo "$(GREEN)Deep cleanup completed!$(NC)"

install-hooks: ## Install git hooks
	@echo "$(GREEN)Installing git hooks...$(NC)"
	@cp $(SCRIPTS_DIR)/git-hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "$(GREEN)Git hooks installed!$(NC)"

status: ## Show project status
	@echo "$(GREEN)Project Status$(NC)"
	@echo ""
	@echo "Backend:"
	@cd $(BACKEND_DIR) && source venv/bin/activate && python --version
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py showmigrations --list | grep "\[ \]" | wc -l | xargs -I {} echo "  Pending migrations: {}"
	@echo ""
	@echo "Frontend:"
	@cd $(FRONTEND_DIR) && node --version
	@cd $(FRONTEND_DIR) && npm --version
	@echo ""
	@echo "Database:"
	@cd $(BACKEND_DIR) && source venv/bin/activate && python manage.py dbshell -c "SELECT COUNT(*) FROM django_migrations;" 2>/dev/null || echo "  Not connected"

.DEFAULT_GOAL := help
