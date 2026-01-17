DOMAIN = "retention_cleaner"

COORDINATOR_UPDATE_INTERVAL_SECONDS = 3600

CONF_BASE_PATH = "base_path"
CONF_PATTERN = "pattern"
CONF_RETENTION_DAYS = "retention_days"
CONF_RUN_AT = "run_at"  # HH:MM
CONF_DRY_RUN = "dry_run"
CONF_MAX_DELETES = "max_deletes"
CONF_ONLY_EXTENSIONS = "only_extensions"
CONF_EXCEPT_EXTENSIONS = "except_extensions"

DEFAULT_PATTERN = "**/*.jpg"
DEFAULT_RETENTION_DAYS = 30
DEFAULT_RUN_AT = "03:15"
DEFAULT_DRY_RUN = False
DEFAULT_MAX_DELETES = 5000

# Pattern constants
ALL_FILES_PATTERN = "**/*"
