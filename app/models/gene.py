from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Gene(Base):
    """Gene reference table with NCBI Gene descriptions and ClinVar stats."""

    __tablename__ = "genes"

    symbol: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))  # short name from NCBI Gene
    summary: Mapped[str | None] = mapped_column(Text)  # functional paragraph from NCBI Gene
    ncbi_gene_id: Mapped[int | None] = mapped_column(Integer)
    omim_number: Mapped[str | None] = mapped_column(String(20))

    # Genomic coordinates (populated from NCBI RefSeq GFF)
    chrom: Mapped[str | None] = mapped_column(String(5))
    start_position_grch37: Mapped[int | None] = mapped_column(Integer)
    end_position_grch37: Mapped[int | None] = mapped_column(Integer)
    start_position_grch38: Mapped[int | None] = mapped_column(Integer)
    end_position_grch38: Mapped[int | None] = mapped_column(Integer)

    # ClinVar gene-level stats (from gene_specific_summary.txt)
    clinvar_total_variants: Mapped[int | None] = mapped_column(Integer)
    clinvar_pathogenic_count: Mapped[int | None] = mapped_column(Integer)
    clinvar_uncertain_count: Mapped[int | None] = mapped_column(Integer)
    clinvar_conflicting_count: Mapped[int | None] = mapped_column(Integer)
    clinvar_total_submissions: Mapped[int | None] = mapped_column(Integer)
