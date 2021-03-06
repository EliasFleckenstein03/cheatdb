"""empty message

Revision ID: 13113e5710da
Revises: ead35f7d446c
Create Date: 2018-05-23 20:18:07.606646

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13113e5710da'
down_revision = 'ead35f7d446c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('package', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('package', 'created_at')
    # ### end Alembic commands ###
