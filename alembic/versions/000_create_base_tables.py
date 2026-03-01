"""Create all base tables.

Revision ID: 000_base
Revises:
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "000_base"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- snpedia_snps ---
    op.create_table(
        "snpedia_snps",
        sa.Column("rsid", sa.String(20), primary_key=True),
    )

    # --- snps ---
    op.create_table(
        "snps",
        sa.Column("rsid", sa.String(), primary_key=True),
        sa.Column("chrom", sa.String(2), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("position_grch38", sa.Integer(), nullable=True),
        sa.Column("ref_allele", sa.String(255), nullable=False),
        sa.Column("alt_allele", sa.String(255), nullable=False),
        sa.Column("gene", sa.String(50), nullable=True, index=True),
        sa.Column("functional_class", sa.String(50), nullable=True),
        sa.Column("maf_global", sa.Float(), nullable=True),
        sa.Column("cadd_phred", sa.Float(), nullable=True),
        sa.Column("sift_category", sa.String(20), nullable=True),
        sa.Column("sift_score", sa.Float(), nullable=True),
        sa.Column("polyphen_category", sa.String(30), nullable=True),
        sa.Column("polyphen_score", sa.Float(), nullable=True),
        sa.Column("revel_score", sa.Float(), nullable=True),
        sa.Column("clinvar_significance", sa.String(100), nullable=True),
        sa.Column("clinvar_conditions", sa.Text(), nullable=True),
        sa.Column("clinvar_review_stars", sa.Integer(), nullable=True),
        sa.Column("clinvar_allele_id", sa.Integer(), nullable=True),
        sa.Column("hgvs_coding", sa.String(255), nullable=True),
        sa.Column("hgvs_protein", sa.String(255), nullable=True),
        sa.Column("gnomad_afr", sa.Float(), nullable=True),
        sa.Column("gnomad_eas", sa.Float(), nullable=True),
        sa.Column("gnomad_nfe", sa.Float(), nullable=True),
        sa.Column("gnomad_sas", sa.Float(), nullable=True),
        sa.Column("gnomad_amr", sa.Float(), nullable=True),
        sa.Column("gnomad_fin", sa.Float(), nullable=True),
        sa.Column("gnomad_asj", sa.Float(), nullable=True),
    )

    # --- snp_trait_associations ---
    op.create_table(
        "snp_trait_associations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rsid", sa.String(), nullable=False, index=True),
        sa.Column("trait", sa.String(255), nullable=False, index=True),
        sa.Column("risk_allele", sa.String(10), nullable=False),
        sa.Column("odds_ratio", sa.Float(), nullable=True),
        sa.Column("beta", sa.Float(), nullable=True),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("effect_description", sa.Text(), nullable=True),
        sa.Column("evidence_level", sa.String(10), nullable=False),
        sa.Column("source_pmid", sa.String(20), nullable=True),
        sa.Column("source_title", sa.Text(), nullable=True),
        sa.Column("trait_prevalence", sa.Float(), nullable=True),
        sa.Column("extraction_method", sa.String(20), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_snp_trait_rsid_trait", "snp_trait_associations", ["rsid", "trait"])

    # --- prs_scores ---
    op.create_table(
        "prs_scores",
        sa.Column("pgs_id", sa.String(20), primary_key=True),
        sa.Column("trait_name", sa.String(255), nullable=False),
        sa.Column("trait_efo_id", sa.String(50), nullable=True),
        sa.Column("publication_pmid", sa.String(20), nullable=True),
        sa.Column("n_variants_total", sa.Integer(), nullable=False),
        sa.Column("n_variants_on_chip", sa.Integer(), nullable=True),
        sa.Column("development_ancestry", sa.String(255), nullable=True),
        sa.Column("validation_ancestry", sa.String(255), nullable=True),
        sa.Column("reported_auc", sa.Float(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- prs_variant_weights ---
    op.create_table(
        "prs_variant_weights",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pgs_id", sa.String(20), nullable=False),
        sa.Column("rsid", sa.String(20), nullable=False),
        sa.Column("chrom", sa.String(2), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("position_grch38", sa.Integer(), nullable=True),
        sa.Column("effect_allele", sa.String(255), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("eur_af", sa.Float(), nullable=True),
        sa.Column("afr_af", sa.Float(), nullable=True),
        sa.Column("eas_af", sa.Float(), nullable=True),
        sa.Column("sas_af", sa.Float(), nullable=True),
        sa.Column("amr_af", sa.Float(), nullable=True),
        sa.Column("effect_is_alt", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_prs_weights_pgs_rsid", "prs_variant_weights", ["pgs_id", "rsid"])

    # --- prs_trait_metadata ---
    op.create_table(
        "prs_trait_metadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pgs_id", sa.String(20), nullable=False, unique=True),
        sa.Column("trait_type", sa.String(20), nullable=False),
        sa.Column("prevalence", sa.Float(), nullable=True),
        sa.Column("population_mean", sa.Float(), nullable=True),
        sa.Column("population_std", sa.Float(), nullable=True),
        sa.Column("source", sa.String(255), nullable=True),
    )

    # --- prs_reference_distributions ---
    op.create_table(
        "prs_reference_distributions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pgs_id", sa.String(20), nullable=False),
        sa.Column("ancestry_group", sa.String(3), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("std", sa.Float(), nullable=False),
        sa.Column("percentiles_json", JSON(), nullable=True),
    )

    # --- analyses ---
    op.create_table(
        "analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("chip_type", sa.String(50), nullable=True),
        sa.Column("variant_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detected_ancestry", JSON(), nullable=True),
        sa.Column("ancestry_method", sa.String(20), nullable=True),
        sa.Column("ancestry_confidence", sa.Float(), nullable=True),
        sa.Column("genome_build", sa.String(10), nullable=True),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("file_format", sa.String(20), nullable=True),
    )

    # --- prs_results ---
    op.create_table(
        "prs_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("pgs_id", sa.String(20), nullable=False),
        sa.Column("raw_score", sa.Float(), nullable=False),
        sa.Column("percentile", sa.Float(), nullable=False),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("ref_mean", sa.Float(), nullable=True),
        sa.Column("ref_std", sa.Float(), nullable=True),
        sa.Column("ancestry_group_used", sa.String(3), nullable=False),
        sa.Column("n_variants_matched", sa.Integer(), nullable=False),
        sa.Column("n_variants_total", sa.Integer(), nullable=False),
        sa.Column("percentile_lower", sa.Float(), nullable=True),
        sa.Column("percentile_upper", sa.Float(), nullable=True),
        sa.Column("coverage_quality", sa.String(10), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- user_snp_trait_hits ---
    op.create_table(
        "user_snp_trait_hits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rsid", sa.String(20), nullable=False),
        sa.Column("user_genotype", sa.String(2), nullable=False),
        sa.Column("trait", sa.String(255), nullable=False),
        sa.Column("effect_description", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("evidence_level", sa.String(10), nullable=False),
        sa.Column("association_id", UUID(as_uuid=True), nullable=False),
    )

    # --- user_variants ---
    op.create_table(
        "user_variants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rsid", sa.String(20), nullable=False),
    )
    op.create_index("ix_user_variants_user_analysis", "user_variants", ["user_id", "analysis_id"])


def downgrade() -> None:
    op.drop_table("user_variants")
    op.drop_table("user_snp_trait_hits")
    op.drop_table("prs_results")
    op.drop_table("analyses")
    op.drop_table("prs_reference_distributions")
    op.drop_table("prs_trait_metadata")
    op.drop_table("prs_variant_weights")
    op.drop_table("prs_scores")
    op.drop_table("snp_trait_associations")
    op.drop_table("snps")
    op.drop_table("snpedia_snps")
