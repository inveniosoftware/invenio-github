# SPDX-FileCopyrightText: 2016-2018 CERN.
# SPDX-License-Identifier: MIT

"""Create github branch."""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5a5428312b2b"
down_revision = None
branch_labels = ("invenio_github",)
depends_on = "dbdbc1b19cf2"


def upgrade():
    """Upgrade database."""
    pass


def downgrade():
    """Downgrade database."""
    pass
