"""add pgvector support

Revision ID: 003
Revises: 002
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 启用 pgvector 扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 添加新的 vector 类型列
    op.execute('ALTER TABLE document_chunks ADD COLUMN embedding_vector vector(768)')

    # 将 JSON 格式的 embedding 数据迁移到 vector 类型
    op.execute("""
        UPDATE document_chunks
        SET embedding_vector = embedding::text::vector
        WHERE embedding IS NOT NULL
    """)

    # 创建 HNSW 索引（用于余弦相似度搜索）
    op.execute("""
        CREATE INDEX idx_document_chunks_embedding_vector
        ON document_chunks
        USING hnsw (embedding_vector vector_cosine_ops)
    """)

    # 删除旧的 JSON 格式 embedding 列
    op.drop_column('document_chunks', 'embedding')

    # 重命名新列
    op.alter_column('document_chunks', 'embedding_vector', new_column_name='embedding')


def downgrade() -> None:
    # 添加回 JSON 格式列
    op.add_column('document_chunks', sa.Column('embedding_json', sa.Text(), nullable=True))

    # 将 vector 数据转回 JSON
    op.execute("""
        UPDATE document_chunks
        SET embedding_json = embedding_vector::text
        WHERE embedding_vector IS NOT NULL
    """)

    # 删除 vector 列和索引
    op.execute('DROP INDEX IF EXISTS idx_document_chunks_embedding_vector')
    op.drop_column('document_chunks', 'embedding_vector')

    # 重命名回原列名
    op.alter_column('document_chunks', 'embedding_json', new_column_name='embedding')
