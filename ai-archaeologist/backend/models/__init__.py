
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models so SQLAlchemy can resolve relationships.
from backend.models.repository import Repository
from backend.models.commit import Commit
from backend.models.contributor import Contributor
from backend.models.issue import Issue
from backend.models.pull_request import PullRequest
from backend.models.repository_file import RepositoryFile
