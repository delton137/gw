"""Add foreign key constraints, indexes, and unique constraints for data integrity.

Revision ID: 019_fk_indexes_constraints
Revises: 018_carrier_status
Create Date: 2026-02-26
"""

from alembic import op

revision = "019_fk_indexes_constraints"
down_revision = "018_carrier_status"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Clean orphaned rows before adding FK constraints ──────────────

    # User result tables → analyses
    for table in [
        "prs_results",
        "user_snp_trait_hits",
        "user_variants",
        "user_pgx_results",
        "user_blood_type_results",
        "user_hla_results",
        "user_carrier_status_results",
    ]:
        op.execute(
            f"DELETE FROM {table} WHERE analysis_id NOT IN (SELECT id FROM analyses)"
        )

    # prs_results.pgs_id → prs_scores
    op.execute(
        "DELETE FROM prs_results WHERE pgs_id NOT IN (SELECT pgs_id FROM prs_scores)"
    )

    # user_snp_trait_hits.association_id → snp_trait_associations
    op.execute(
        "DELETE FROM user_snp_trait_hits WHERE association_id NOT IN (SELECT id FROM snp_trait_associations)"
    )

    # Knowledge base tables → prs_scores
    for table in ["prs_variant_weights", "prs_trait_metadata", "prs_reference_distributions"]:
        op.execute(
            f"DELETE FROM {table} WHERE pgs_id NOT IN (SELECT pgs_id FROM prs_scores)"
        )

    # pgx_allele_phenotypes.annotation_id → pgx_clinical_annotations
    op.execute(
        "DELETE FROM pgx_allele_phenotypes WHERE annotation_id NOT IN (SELECT id FROM pgx_clinical_annotations)"
    )

    # pgx_star_allele_definitions.gene → pgx_gene_definitions
    op.execute(
        "DELETE FROM pgx_star_allele_definitions WHERE gene NOT IN (SELECT gene FROM pgx_gene_definitions)"
    )

    # ── 2. Deduplicate rows before adding unique constraints ─────────────

    # prs_reference_distributions: keep lowest id per (pgs_id, ancestry_group)
    op.execute("""
        DELETE FROM prs_reference_distributions
        WHERE id NOT IN (
            SELECT MIN(id) FROM prs_reference_distributions
            GROUP BY pgs_id, ancestry_group
        )
    """)

    # pgx_diplotype_phenotypes: keep lowest id per (gene, function_pair)
    op.execute("""
        DELETE FROM pgx_diplotype_phenotypes
        WHERE id NOT IN (
            SELECT MIN(id) FROM pgx_diplotype_phenotypes
            GROUP BY gene, function_pair
        )
    """)

    # user_variants: keep lowest id per (user_id, analysis_id, rsid)
    op.execute("""
        DELETE FROM user_variants
        WHERE id NOT IN (
            SELECT MIN(id) FROM user_variants
            GROUP BY user_id, analysis_id, rsid
        )
    """)

    # ── 3. Foreign key constraints ───────────────────────────────────────

    # User result tables → analyses.id
    op.create_foreign_key(
        "fk_prs_results_analysis", "prs_results", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_prs_results_pgs", "prs_results", "prs_scores",
        ["pgs_id"], ["pgs_id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_trait_hits_analysis", "user_snp_trait_hits", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_trait_hits_association", "user_snp_trait_hits", "snp_trait_associations",
        ["association_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_variants_analysis", "user_variants", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_pgx_results_analysis", "user_pgx_results", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_bt_results_analysis", "user_blood_type_results", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_hla_results_analysis", "user_hla_results", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_cs_results_analysis", "user_carrier_status_results", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )

    # Knowledge base tables → prs_scores
    op.create_foreign_key(
        "fk_prs_weights_pgs", "prs_variant_weights", "prs_scores",
        ["pgs_id"], ["pgs_id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_prs_metadata_pgs", "prs_trait_metadata", "prs_scores",
        ["pgs_id"], ["pgs_id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_prs_ref_dist_pgs", "prs_reference_distributions", "prs_scores",
        ["pgs_id"], ["pgs_id"], ondelete="CASCADE",
    )

    # PGX knowledge base
    op.create_foreign_key(
        "fk_pgx_ap_annotation", "pgx_allele_phenotypes", "pgx_clinical_annotations",
        ["annotation_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pgx_star_gene", "pgx_star_allele_definitions", "pgx_gene_definitions",
        ["gene"], ["gene"], ondelete="CASCADE",
    )

    # ── 4. Indexes ───────────────────────────────────────────────────────

    op.create_index(
        "ix_analyses_user_status_created",
        "analyses",
        ["user_id", "status", "created_at"],
    )
    op.create_index(
        "ix_prs_results_analysis_id",
        "prs_results",
        ["analysis_id"],
    )
    op.create_index(
        "ix_user_trait_hits_analysis_id",
        "user_snp_trait_hits",
        ["analysis_id"],
    )
    op.create_index(
        "ix_prs_weights_rsid",
        "prs_variant_weights",
        ["rsid"],
    )

    # ── 5. Unique constraints ────────────────────────────────────────────

    op.create_unique_constraint(
        "uq_prs_ref_dist_pgs_ancestry",
        "prs_reference_distributions",
        ["pgs_id", "ancestry_group"],
    )
    op.create_unique_constraint(
        "uq_pgx_diplo_gene_funcpair",
        "pgx_diplotype_phenotypes",
        ["gene", "function_pair"],
    )
    op.create_unique_constraint(
        "uq_user_variants_user_analysis_rsid",
        "user_variants",
        ["user_id", "analysis_id", "rsid"],
    )


def downgrade():
    # Unique constraints
    op.drop_constraint("uq_user_variants_user_analysis_rsid", "user_variants")
    op.drop_constraint("uq_pgx_diplo_gene_funcpair", "pgx_diplotype_phenotypes")
    op.drop_constraint("uq_prs_ref_dist_pgs_ancestry", "prs_reference_distributions")

    # Indexes
    op.drop_index("ix_prs_weights_rsid", "prs_variant_weights")
    op.drop_index("ix_user_trait_hits_analysis_id", "user_snp_trait_hits")
    op.drop_index("ix_prs_results_analysis_id", "prs_results")
    op.drop_index("ix_analyses_user_status_created", "analyses")

    # Foreign keys
    op.drop_constraint("fk_pgx_star_gene", "pgx_star_allele_definitions")
    op.drop_constraint("fk_pgx_ap_annotation", "pgx_allele_phenotypes")
    op.drop_constraint("fk_prs_ref_dist_pgs", "prs_reference_distributions")
    op.drop_constraint("fk_prs_metadata_pgs", "prs_trait_metadata")
    op.drop_constraint("fk_prs_weights_pgs", "prs_variant_weights")
    op.drop_constraint("fk_user_cs_results_analysis", "user_carrier_status_results")
    op.drop_constraint("fk_user_hla_results_analysis", "user_hla_results")
    op.drop_constraint("fk_user_bt_results_analysis", "user_blood_type_results")
    op.drop_constraint("fk_user_pgx_results_analysis", "user_pgx_results")
    op.drop_constraint("fk_user_variants_analysis", "user_variants")
    op.drop_constraint("fk_user_trait_hits_association", "user_snp_trait_hits")
    op.drop_constraint("fk_user_trait_hits_analysis", "user_snp_trait_hits")
    op.drop_constraint("fk_prs_results_pgs", "prs_results")
    op.drop_constraint("fk_prs_results_analysis", "prs_results")
