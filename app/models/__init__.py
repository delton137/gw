from app.models.base import Base
from app.models.gene import Gene
from app.models.carrier_status import UserCarrierStatusResult
from app.models.gwas import GwasAssociation, GwasPrsResult, GwasReferenceDistribution, GwasStudy
from app.models.newsletter import EmailSubscriber
from app.models.pgx import (
    PgxDiplotypePhenotype,
    PgxDrugGuideline,
    PgxGeneDefinition,
    PgxStarAlleleDefinition,
    UserPgxResult,
)
from app.models.prs import PrsReferenceDistribution, PrsScore, PrsTraitMetadata, PrsVariantWeight
from app.models.snp import Snp, SnpTraitAssociation, SnpediaSnp
from app.models.user import Analysis, PrsResult, UserClinvarHit, UserSnpTraitHit, UserVariant

__all__ = [
    "Base",
    # snp
    "Snp",
    "SnpTraitAssociation",
    "SnpediaSnp",
    # gene
    "Gene",
    # prs
    "PrsScore",
    "PrsVariantWeight",
    "PrsReferenceDistribution",
    "PrsTraitMetadata",
    # gwas
    "GwasStudy",
    "GwasAssociation",
    "GwasReferenceDistribution",
    "GwasPrsResult",
    # user
    "Analysis",
    "PrsResult",
    "UserClinvarHit",
    "UserSnpTraitHit",
    "UserVariant",
    # pgx
    "PgxGeneDefinition",
    "PgxStarAlleleDefinition",
    "PgxDiplotypePhenotype",
    "PgxDrugGuideline",
    "UserPgxResult",
    # carrier status
    "UserCarrierStatusResult",
    # newsletter
    "EmailSubscriber",
]
