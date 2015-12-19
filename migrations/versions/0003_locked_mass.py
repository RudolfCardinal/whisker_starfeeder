"""locked_mass

Revision ID: 0003
Revises: 0002
Create Date: 2015-12-19 00:03:04.517156

"""

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('balance_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('unlock_mass_kg', sa.Float(), nullable=True))

    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('balance_config', schema=None) as batch_op:
        batch_op.drop_column('unlock_mass_kg')

    ### end Alembic commands ###
