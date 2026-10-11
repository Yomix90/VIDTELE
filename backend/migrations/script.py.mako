"""${message}

Révision : ${up_revision}
Précédente : ${down_revision | comma,n}
Créée le : ${create_date}

Règles :
- upgrade() ne doit jamais perdre de données (ajouter plutôt que supprimer/renommer).
- downgrade() doit ramener exactement au schéma précédent.
- Tester sur une COPIE de la base de production avant de fusionner dans main.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
