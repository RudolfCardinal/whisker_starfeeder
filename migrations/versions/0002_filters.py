"""filters

Revision ID: 0002
Revises: 0001
Create Date: 2015-12-16 12:59:20.778648

"""

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('balance_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('amp_signal_filter_mode', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('fast_response_filter', sa.Boolean(), nullable=True))

    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('balance_config', schema=None) as batch_op:
        batch_op.drop_column('fast_response_filter')
        batch_op.drop_column('amp_signal_filter_mode')

    ### end Alembic commands ###