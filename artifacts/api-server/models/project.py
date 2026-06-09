from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # The tutorial request — what the user wants a tutorial/walkthrough on.
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tutorial request controls
    skill_level: Mapped[str | None] = mapped_column(String(50), nullable=True)      # beginner | intermediate | advanced
    tutorial_type: Mapped[str | None] = mapped_column(String(100), nullable=True)   # overview | hands-on-build | debugging | architecture | deployment
    stack: Mapped[str | None] = mapped_column(Text, nullable=True)                  # language / framework / stack
    platform: Mapped[str | None] = mapped_column(String(200), nullable=True)        # platform / environment
    depth: Mapped[str | None] = mapped_column(String(50), nullable=True)            # quick | standard | deep-dive
    include_code: Mapped[bool] = mapped_column(default=True, nullable=False)        # include code snippets
    output_style: Mapped[str | None] = mapped_column(String(100), nullable=True)    # concise | detailed | checklist-driven | project-based
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)            # time budget, preferred tools, things to avoid

    formatting_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    artifact_density: Mapped[str | None] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
