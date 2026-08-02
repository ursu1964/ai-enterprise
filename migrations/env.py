from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from ai_enterprise.config import get_settings
from ai_enterprise.infrastructure.agent_runtime import (
    models as agent_runtime_models,  # noqa: F401
)
from ai_enterprise.infrastructure.architecture import (
    models as architecture_models,  # noqa: F401
)
from ai_enterprise.infrastructure.change_management import (
    models as change_models,  # noqa: F401
)
from ai_enterprise.infrastructure.cognitive import (
    models as cognitive_models,  # noqa: F401
)
from ai_enterprise.infrastructure.database import (
    foundation_models,  # noqa: F401
    workflow_models,  # noqa: F401
)
from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.infrastructure.decomposition import (
    models as decomposition_models,  # noqa: F401
)
from ai_enterprise.infrastructure.ecosystem import (
    models as ecosystem_models,  # noqa: F401
)
from ai_enterprise.infrastructure.enterprise_evolution import (  # noqa: F401
    models as enterprise_evolution_models,
)
from ai_enterprise.infrastructure.evolution import (
    models as evolution_models,  # noqa: F401
)
from ai_enterprise.infrastructure.jobs import models as job_models  # noqa: F401
from ai_enterprise.infrastructure.knowledge import (
    models as knowledge_models,  # noqa: F401
)
from ai_enterprise.infrastructure.performance import (
    models as performance_models,  # noqa: F401
)
from ai_enterprise.infrastructure.requirements_revision import (  # noqa: F401
    models as requirements_revision_models,
)
from ai_enterprise.infrastructure.resilience import (
    extended_models as resilience_extended_models,  # noqa: F401
)
from ai_enterprise.infrastructure.resilience import (
    models as resilience_models,  # noqa: F401
)
from ai_enterprise.infrastructure.specification import (
    models as specification_models,  # noqa: F401
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

database_url = get_settings().database_url
if database_url.startswith("postgresql+asyncpg://"):
    database_url = database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
    )
config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
