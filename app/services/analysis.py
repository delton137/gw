"""Analysis pipeline — parse genotype file, run fast analyses, then PRS in background.

Runs as an asyncio background task. CPU-heavy work (file I/O, parsing, scoring)
runs in threads to keep the event loop responsive. Raw file content is deleted
immediately after parsing.

Pipeline order:
  1. Parse genotype file (status: parsing)
  2. Match SNPedia variants (status: matching_snpedia)
  3. Parallel fast matching (status: matching_fast):
     - Trait associations, ClinVar, PGx (DB-bound, separate sessions)
     - Blood type, carrier status (CPU-only, threaded)
  4. Commit fast results → status: done  (frontend redirects to dashboard)
  5. Background: ancestry estimation + PRS scoring (status: scoring_prs)
  6. Complete → status: complete
"""

from __future__ import annotations

import asyncio
try:
    from isal import igzip as gzip
except ImportError:
    import gzip
import logging
import os
import time
from datetime import datetime, timezone

import polars as pl
from sqlalchemy import column as sa_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session_factory
from app.models.blood_type import UserBloodTypeResult
from app.models.carrier_status import UserCarrierStatusResult
from app.models.prs import PrsScore, PrsReferenceDistribution
from app.models.pgx import UserPgxResult
from app.models.user import Analysis, PrsResult, UserClinvarHit, UserSnpTraitHit, UserVariant
from app.services.ancestry_estimator import estimate_ancestry
from app.services.clinvar_matcher import match_clinvar
from app.services.blood_type import determine_blood_type, BLOOD_TYPE_DELETION_RSIDS
from app.services.carrier_matcher import determine_carrier_status
from app.services.parser import parse_genotype_file, extract_raw_genotypes, detect_genome_build, ParseError
from app.services.pgx_matcher import match_pgx
from app.services.scorer import compute_prs
from app.services.trait_matcher import match_traits

log = logging.getLogger(__name__)

# Limit concurrent parse+score operations to avoid OOM on 8GB servers.
_analysis_semaphore = asyncio.Semaphore(1)

from app.services.data_loader import load_pgx_positions_list


async def run_analysis_pipeline(
    analysis_id: str,
    user_id: str,
    tmp_path: str,
    ancestry_group: str,
    session: AsyncSession,
) -> None:
    """Unified analysis pipeline — fast results first, then PRS in background.

    Serialized via semaphore to prevent OOM from concurrent uploads.
    """
    if _analysis_semaphore.locked():
        await session.execute(
            text("UPDATE analyses SET status_detail = :d WHERE id = :id"),
            {"d": "Queued — another analysis is running", "id": analysis_id},
        )
        await session.commit()
    async with _analysis_semaphore:
        await _run_pipeline(analysis_id, user_id, tmp_path, ancestry_group, session)


async def _set_detail(
    analysis: Analysis, session: AsyncSession, detail: str, *, status: str | None = None,
) -> None:
    """Update status_detail (and optionally status) then commit once."""
    analysis.status_detail = detail
    if status:
        analysis.status = status
    await session.commit()


async def _fail_analysis(
    session: AsyncSession,
    analysis: "Analysis",
    error_message: str,
    *,
    set_failed: bool = True,
    tmp_path: str | None = None,
) -> None:
    """Rollback, record an error message, and optionally clean up the temp file."""
    try:
        await session.rollback()
        if set_failed:
            analysis.status = "failed"
        analysis.error_message = error_message
        await session.commit()
    except Exception:
        pass
    if tmp_path:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass


async def _run_pipeline(
    analysis_id: str,
    user_id: str,
    tmp_path: str,
    ancestry_group: str,
    session: AsyncSession,
) -> None:
    t_total = time.perf_counter()

    result = await session.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        log.error(f"Analysis {analysis_id} not found")
        return

    try:
        # =================================================================
        # STEP 1: Parse genotype file (CPU-heavy, runs in thread)
        # =================================================================
        analysis.status = "parsing"
        await session.commit()
        t0 = time.perf_counter()

        def _parse_file() -> tuple:
            """Read, decompress, and parse genotype file. Runs in a thread."""
            try:
                with open(tmp_path, "rb") as f:
                    file_bytes = f.read()
            finally:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

            if file_bytes[:2] == b"\x1f\x8b":
                log.info(f"[{analysis_id}] Decompressing gzip ({len(file_bytes) / 1024 / 1024:.0f} MB compressed)...")
                decompressed = gzip.decompress(file_bytes)
                decompressed_mb = len(decompressed) / 1024 / 1024
                log.info(f"[{analysis_id}] Decompressed to {decompressed_mb:.0f} MB")
                del file_bytes
                if len(decompressed) > settings.max_decompressed_size:
                    raise ParseError("Decompressed file exceeds 10GB size limit")
                content = decompressed.decode("utf-8", errors="replace")
                del decompressed
            else:
                content = file_bytes.decode("utf-8", errors="replace")
                del file_bytes

            result = parse_genotype_file(content)
            # Extract deletion genotypes for blood type (rs8176719 on DTC chips)
            deletion_gts = extract_raw_genotypes(content, result[1], BLOOD_TYPE_DELETION_RSIDS)
            del content
            return (*result, deletion_gts)

        user_df, fmt, chip_version, deletion_genotypes = await asyncio.to_thread(_parse_file)

        elapsed_parse = time.perf_counter() - t0
        log.info(f"[{analysis_id}] Parsed {len(user_df)} variants ({fmt}/{chip_version}) in {elapsed_parse:.2f}s")
        await _set_detail(analysis, session, f"Parsed {len(user_df):,} variants ({fmt} format)")

        # Detect genome build (needed for blood type position matching + VCF rsID lookup)
        genome_build = detect_genome_build(user_df)
        if genome_build == "unknown":
            await _fail_analysis(
                session, analysis,
                "Unable to determine genome build. GeneWizard supports GRCh37 (hg19) and "
                "GRCh38 (hg38) only. Please verify your file was generated against a "
                "standard human reference genome and try again.",
                tmp_path=tmp_path,
            )
            return
        analysis.genome_build = genome_build
        log.info(f"[{analysis_id}] Detected genome build: {genome_build}")

        # For WGS VCFs with "." rsids, annotate using comprehensive position lookup
        dot_count = user_df.filter(pl.col("rsid") == ".").height
        has_dot_rsids = dot_count > 0
        if has_dot_rsids:
            log.info(f"[{analysis_id}] {dot_count} variants lack rsIDs — building comprehensive annotation lookup...")
            t_lookup = time.perf_counter()
            await _set_detail(analysis, session, f"Detected genome build: {genome_build}")

            _POS_COL = {"GRCh38": "position_grch38", "GRCh37": "position"}
            pos_col_name = _POS_COL.get(genome_build, "position")

            # Run annotation source queries in parallel (separate sessions)
            async def _query_snp_positions() -> list[tuple[str, str, int]]:
                from app.models.snp import Snp
                pos_col = sa_column(pos_col_name)
                async with async_session_factory() as s:
                    result = await s.execute(
                        select(Snp.rsid, Snp.chrom, pos_col.label("pos"))
                        .select_from(Snp.__table__)
                        .where(pos_col.isnot(None))
                    )
                    return [(r.rsid, r.chrom, r.pos) for r in result.fetchall()]

            async def _query_prs_positions() -> list[tuple[str, str, int]]:
                if genome_build == "GRCh38":
                    sql = """
                        SELECT DISTINCT rsid, chrom, position_grch38 AS pos
                        FROM prs_variant_weights
                        WHERE rsid IS NOT NULL AND rsid != '.'
                          AND position_grch38 IS NOT NULL
                    """
                else:
                    sql = """
                        SELECT DISTINCT rsid, chrom, position AS pos
                        FROM prs_variant_weights
                        WHERE rsid IS NOT NULL AND rsid != '.'
                          AND position IS NOT NULL
                    """
                async with async_session_factory() as s:
                    result = await s.execute(text(sql))
                    return [(r.rsid, r.chrom, r.pos) for r in result.fetchall()]

            snp_rows, prs_rows = await asyncio.gather(
                _query_snp_positions(),
                _query_prs_positions(),
            )
            # Source 3: PGx allele-defining variants (1,333 positions) — sync, cached
            pgx_positions = load_pgx_positions_list(genome_build)

            annotation_rows: list[tuple[str, str, int]] = snp_rows + prs_rows + pgx_positions

            if annotation_rows:
                # Deduplicate: for each (chrom, pos), prefer rsid starting with "rs"
                seen: dict[tuple[str, int], str] = {}
                for rsid, chrom, pos in annotation_rows:
                    key = (str(chrom), int(pos))
                    if key not in seen or (not seen[key].startswith("rs") and rsid.startswith("rs")):
                        seen[key] = rsid

                snp_lookup = pl.DataFrame(
                    {
                        "chrom": [k[0] for k in seen],
                        "position": [k[1] for k in seen],
                        "known_rsid": [v for v in seen.values()],
                    },
                    schema={"chrom": pl.Utf8, "position": pl.Int64, "known_rsid": pl.Utf8},
                )

                log.info(f"[{analysis_id}] Built annotation lookup with {len(snp_lookup)} positions")

                user_df = user_df.join(snp_lookup, on=["chrom", "position"], how="left")
                user_df = user_df.with_columns(
                    pl.when(pl.col("rsid") == ".")
                    .then(pl.col("known_rsid"))
                    .otherwise(pl.col("rsid"))
                    .alias("rsid")
                ).drop("known_rsid")

                annotated_count = user_df.filter(
                    pl.col("rsid").is_not_null() & (pl.col("rsid") != ".")
                ).height
                log.info(
                    f"[{analysis_id}] Annotated {annotated_count:,} of {user_df.height:,} variants "
                    f"({genome_build} positions) in {time.perf_counter() - t_lookup:.2f}s"
                )
            else:
                log.warning(f"[{analysis_id}] No position data in database — cannot annotate VCF rsIDs")

        # Split DataFrames: full (for position-based services) vs annotated (for rsid-based services)
        user_df_full = user_df  # all variants including "." rsids
        user_df = user_df_full.filter(pl.col("rsid").is_not_null() & (pl.col("rsid") != "."))

        analysis.chip_type = chip_version
        analysis.variant_count = len(user_df_full) if has_dot_rsids else len(user_df)
        analysis.file_format = fmt
        analysis.selected_ancestry = ancestry_group
        await session.commit()

        is_vcf = fmt in ("vcf", "cgi") if fmt else False
        is_wgs = is_vcf and chip_version == "wgs"

        # =================================================================
        # STEP 2: Fast matching (individual status per sub-step)
        # =================================================================

        # ----- SNPedia variant storage -----
        analysis.status = "matching_snpedia"
        await session.commit()
        t_var = time.perf_counter()
        snpedia_result = await session.execute(text("SELECT rsid FROM snpedia_snps"))
        snpedia_rsids = {row.rsid for row in snpedia_result}

        if snpedia_rsids:
            user_rsids = user_df["rsid"].to_list()
            matched_rsids = list(set(user_rsids) & snpedia_rsids)

            if matched_rsids:
                batch_size = 5000
                for i in range(0, len(matched_rsids), batch_size):
                    batch = matched_rsids[i : i + batch_size]
                    session.add_all([
                        UserVariant(user_id=user_id, analysis_id=analysis_id, rsid=rsid)
                        for rsid in batch
                    ])
                await session.commit()

            log.info(
                f"[{analysis_id}] Stored {len(matched_rsids):,} SNPedia-listed variants "
                f"(of {len(user_rsids):,} total) in {time.perf_counter() - t_var:.2f}s"
            )
        else:
            log.warning(f"[{analysis_id}] snpedia_snps table is empty — skipping variant storage")

        # ----- Parallel fast matching (DB + CPU tasks) -----
        analysis.status = "matching_fast"
        analysis.status_detail = "Running trait, ClinVar, PGx, blood type, and carrier matching..."
        await session.commit()
        t0_match = time.perf_counter()

        # DB-bound tasks get their own sessions (AsyncSession is not concurrent-safe)
        async def _run_traits():
            async with async_session_factory() as s:
                return await match_traits(user_df, s, is_vcf=is_wgs)

        async def _run_clinvar():
            async with async_session_factory() as s:
                return await match_clinvar(user_df, s)

        async def _run_pgx():
            async with async_session_factory() as s:
                return await match_pgx(user_df_full, s, genome_build=genome_build, is_vcf=is_vcf)

        # CPU-only tasks run in threads
        trait_hits, clinvar_hits, pgx_results, blood_type_result, carrier_results = (
            await asyncio.gather(
                _run_traits(),
                _run_clinvar(),
                _run_pgx(),
                asyncio.to_thread(
                    determine_blood_type, user_df_full,
                    genome_build=genome_build, deletion_genotypes=deletion_genotypes,
                ),
                asyncio.to_thread(determine_carrier_status, user_df_full, genome_build=genome_build, is_vcf=is_vcf),
            )
        )

        elapsed_match = time.perf_counter() - t0_match
        log.info(
            f"[{analysis_id}] Parallel matching complete in {elapsed_match:.2f}s — "
            f"traits={len(trait_hits)}, clinvar={len(clinvar_hits)}, pgx={len(pgx_results)}"
        )

        # ----- Store results (sequential DB writes using main session) -----
        for i in range(0, len(trait_hits), 5000):
            batch = trait_hits[i : i + 5000]
            session.add_all([
                UserSnpTraitHit(
                    user_id=user_id,
                    analysis_id=analysis_id,
                    rsid=hit.rsid,
                    user_genotype=hit.user_genotype,
                    trait=hit.trait,
                    effect_description=hit.effect_description,
                    risk_level=hit.risk_level,
                    evidence_level=hit.evidence_level,
                    association_id=hit.association_id,
                )
                for hit in batch
            ])

        for i in range(0, len(clinvar_hits), 5000):
            batch = clinvar_hits[i : i + 5000]
            session.add_all([
                UserClinvarHit(
                    user_id=user_id,
                    analysis_id=analysis_id,
                    rsid=hit.rsid,
                    user_genotype=hit.user_genotype,
                )
                for hit in batch
            ])

        for pr in pgx_results:
            session.add(UserPgxResult(
                user_id=user_id,
                analysis_id=analysis_id,
                gene=pr.gene,
                diplotype=pr.diplotype,
                allele1=pr.allele1,
                allele2=pr.allele2,
                allele1_function=pr.allele1_function,
                allele2_function=pr.allele2_function,
                phenotype=pr.phenotype,
                activity_score=pr.activity_score,
                n_variants_tested=pr.n_variants_tested,
                n_variants_total=pr.n_variants_total,
                calling_method=pr.calling_method,
                confidence=pr.confidence,
                drugs_affected=pr.drugs_affected,
                clinical_note=pr.clinical_note,
                variant_genotypes=pr.variant_genotypes,
            ))

        if blood_type_result:
            session.add(UserBloodTypeResult(
                user_id=user_id,
                analysis_id=analysis_id,
                abo_genotype=blood_type_result.abo_genotype,
                abo_phenotype=blood_type_result.abo_phenotype,
                rh_c_antigen=blood_type_result.rh_c_antigen,
                rh_e_antigen=blood_type_result.rh_e_antigen,
                rh_cw_antigen=blood_type_result.rh_cw_antigen,
                kell_phenotype=blood_type_result.kell_phenotype,
                mns_phenotype=blood_type_result.mns_phenotype,
                duffy_phenotype=blood_type_result.duffy_phenotype,
                kidd_phenotype=blood_type_result.kidd_phenotype,
                secretor_status=blood_type_result.secretor_status,
                display_type=blood_type_result.display_type,
                systems_json=blood_type_result.systems or None,
                n_variants_tested=blood_type_result.n_variants_tested,
                n_variants_total=blood_type_result.n_variants_total,
                n_systems_determined=blood_type_result.n_systems_determined,
                confidence=blood_type_result.confidence,
                confidence_note=blood_type_result.confidence_note,
            ))
            log.info(
                f"[{analysis_id}] Blood type: {blood_type_result.display_type} "
                f"({blood_type_result.confidence}, {blood_type_result.n_variants_tested}/{blood_type_result.n_variants_total} variants)"
            )
        else:
            log.info(f"[{analysis_id}] Blood type: insufficient variants for determination")

        n_carrier = sum(1 for r in carrier_results if r.status == "carrier")
        n_affected = sum(1 for r in carrier_results if r.status in ("likely_affected", "potential_compound_het"))
        session.add(UserCarrierStatusResult(
            user_id=user_id,
            analysis_id=analysis_id,
            results_json={r.gene: r.to_dict() for r in carrier_results},
            n_genes_screened=len(carrier_results),
            n_carrier_genes=n_carrier,
            n_affected_flags=n_affected,
        ))
        log.info(
            f"[{analysis_id}] Carrier status: {len(carrier_results)} genes screened, "
            f"{n_carrier} carrier, {n_affected} affected/compound-het"
        )

        # =================================================================
        # STEP 3: Commit fast results — frontend can redirect to dashboard
        # =================================================================
        elapsed_fast = time.perf_counter() - t_total
        analysis.status = "done"
        analysis.pipeline_fast_seconds = round(elapsed_fast, 2)
        await session.commit()
        log.info(
            f"[{analysis_id}] Fast steps complete in {elapsed_fast:.2f}s "
            f"(parse={elapsed_parse:.2f}s, parallel_match={elapsed_match:.2f}s)"
        )

    except asyncio.CancelledError:
        log.warning(f"[{analysis_id}] Analysis cancelled (server shutting down)")
        await _fail_analysis(
            session, analysis,
            "Analysis interrupted by server shutdown. Please re-upload.",
            tmp_path=tmp_path,
        )
        return

    except Exception as e:
        log.error(f"[{analysis_id}] Analysis failed: {e}", exc_info=True)
        await _fail_analysis(
            session, analysis,
            "Analysis failed. Please try again or contact support.",
            tmp_path=tmp_path,
        )
        return

    # =================================================================
    # STEP 4-5: Background — ancestry estimation + PRS scoring
    # These run after "done" so fast results are already visible.
    # =================================================================
    try:
        analysis.status = "scoring_prs"
        analysis.status_detail = "Estimating genetic ancestry..."
        await session.commit()

        # ----- Ancestry estimation (for comparison display) -----
        t_anc = time.perf_counter()
        ancestry_result = await asyncio.to_thread(
            estimate_ancestry, user_df_full, is_vcf, genome_build
        )

        if ancestry_result:
            # Store full ancestry detail as JSON (26 populations + metadata)
            analysis.detected_ancestry = {
                "populations": ancestry_result.populations,
                "superpopulations": ancestry_result.superpopulations,
                "n_markers_used": ancestry_result.n_markers_used,
                "n_markers_total": ancestry_result.n_markers_total,
                "coverage_quality": ancestry_result.coverage_quality,
                "is_admixed": ancestry_result.is_admixed,
            }
            analysis.ancestry_method = "aeon_mle"
            analysis.ancestry_confidence = ancestry_result.confidence
            log.info(
                f"[{analysis_id}] Ancestry estimated: {ancestry_result.best_pop} "
                f"({ancestry_result.confidence:.0%}, {ancestry_result.n_markers_used} AIMs) "
                f"in {time.perf_counter() - t_anc:.2f}s"
            )
            # Build a readable ancestry summary from superpopulations
            top_pops = sorted(
                ancestry_result.superpopulations.items(), key=lambda x: x[1], reverse=True
            )
            anc_summary = ", ".join(f"{v:.0%} {k}" for k, v in top_pops if v >= 0.05)
            analysis.status_detail = f"Detected ancestry: {anc_summary}"
        else:
            analysis.ancestry_method = "computed_failed"
            log.warning(f"[{analysis_id}] Ancestry estimation failed (too few AIMs)")
            analysis.status_detail = "Ancestry estimation: insufficient markers"
        await session.commit()

        # ----- PRS scoring (disabled via settings.prs_enabled) -----
        elapsed_prs = 0.0
        if settings.prs_enabled:
            t0_prs = time.perf_counter()

            scores_result = await session.execute(select(PrsScore))
            prs_scores = scores_result.scalars().all()

            # Batch-load ALL weights and reference distributions (2 queries instead of ~2N)
            all_weights_result = await session.execute(
                text("""
                    SELECT pgs_id, rsid, chrom, position, position_grch38,
                           effect_allele, weight,
                           eur_af, afr_af, eas_af, sas_af, amr_af,
                           effect_is_alt
                    FROM prs_variant_weights
                """)
            )
            all_weight_rows = all_weights_result.fetchall()
            all_weights_df = pl.DataFrame(
                {
                    "pgs_id": [r.pgs_id for r in all_weight_rows],
                    "rsid": [r.rsid for r in all_weight_rows],
                    "chrom": [r.chrom for r in all_weight_rows],
                    "w_position": [r.position for r in all_weight_rows],
                    "w_position_grch38": [r.position_grch38 for r in all_weight_rows],
                    "effect_allele": [r.effect_allele for r in all_weight_rows],
                    "weight": [r.weight for r in all_weight_rows],
                    "eur_af": [r.eur_af for r in all_weight_rows],
                    "afr_af": [r.afr_af for r in all_weight_rows],
                    "eas_af": [r.eas_af for r in all_weight_rows],
                    "sas_af": [r.sas_af for r in all_weight_rows],
                    "amr_af": [r.amr_af for r in all_weight_rows],
                    "effect_is_alt": [r.effect_is_alt for r in all_weight_rows],
                },
                schema={
                    "pgs_id": pl.Utf8,
                    "rsid": pl.Utf8,
                    "chrom": pl.Utf8,
                    "w_position": pl.Int64,
                    "w_position_grch38": pl.Int64,
                    "effect_allele": pl.Utf8,
                    "weight": pl.Float64,
                    "eur_af": pl.Float64,
                    "afr_af": pl.Float64,
                    "eas_af": pl.Float64,
                    "sas_af": pl.Float64,
                    "amr_af": pl.Float64,
                    "effect_is_alt": pl.Boolean,
                },
            )
            del all_weight_rows  # free memory
            weights_by_pgs = {
                df["pgs_id"][0]: df.drop("pgs_id")
                for df in all_weights_df.partition_by("pgs_id")
            }
            del all_weights_df

            all_refs_result = await session.execute(
                select(PrsReferenceDistribution).where(
                    PrsReferenceDistribution.ancestry_group == ancestry_group,
                )
            )
            ref_by_pgs = {r.pgs_id: r for r in all_refs_result.scalars()}

            prs_results_to_store = []
            n_total = len(prs_scores)

            for i, prs_score in enumerate(prs_scores, 1):
                log.debug(f"[{analysis_id}] Scoring PRS {i}/{n_total}: {prs_score.pgs_id}")
                await _set_detail(analysis, session, f"Computing PRS {i}/{n_total}: {prs_score.trait_name or prs_score.pgs_id}")

                weights_df = weights_by_pgs.get(prs_score.pgs_id)
                if weights_df is None:
                    continue

                ref_dist = ref_by_pgs.get(prs_score.pgs_id)
                ref_sorted_scores = None
                if ref_dist:
                    ref_mean = ref_dist.mean
                    ref_std = ref_dist.std
                    # Extract empirical sorted scores for percentile lookup
                    if ref_dist.percentiles_json and isinstance(ref_dist.percentiles_json, dict):
                        ref_sorted_scores = ref_dist.percentiles_json.get("sorted_scores")
                else:
                    log.warning(
                        f"[{analysis_id}] No pre-computed reference distribution for "
                        f"{prs_score.pgs_id}/{ancestry_group} — will use matched-variant AFs"
                    )
                    ref_mean = 0.0
                    ref_std = 0.0

                prs_result = await asyncio.to_thread(
                    compute_prs,
                    user_df=user_df_full,
                    pgs_id=prs_score.pgs_id,
                    weights_df=weights_df,
                    ref_mean=ref_mean,
                    ref_std=ref_std,
                    ancestry_group=ancestry_group,
                    ancestry_weights=None,
                    genome_build=genome_build,
                    ref_sorted_scores=ref_sorted_scores,
                )

                if prs_result.n_variants_matched > 0:
                    prs_results_to_store.append(prs_result)

            del weights_by_pgs, ref_by_pgs  # free batch data

            elapsed_prs = time.perf_counter() - t0_prs
            log.info(f"[{analysis_id}] Scored {len(prs_results_to_store)} PRS in {elapsed_prs:.2f}s")

            for pr in prs_results_to_store:
                session.add(PrsResult(
                    user_id=user_id,
                    analysis_id=analysis_id,
                    pgs_id=pr.pgs_id,
                    raw_score=pr.raw_score,
                    percentile=pr.percentile,
                    z_score=pr.z_score,
                    ref_mean=pr.ref_mean,
                    ref_std=pr.ref_std,
                    ancestry_group_used=pr.ancestry_group_used,
                    n_variants_matched=pr.n_variants_matched,
                    n_variants_total=pr.n_variants_total,
                    percentile_lower=pr.percentile_lower,
                    percentile_upper=pr.percentile_upper,
                    coverage_quality=pr.coverage_quality,
                ))
        else:
            log.info(f"[{analysis_id}] PRS scoring disabled (settings.prs_enabled=False)")

        # ----- GWAS-hit PRS scoring (non-fatal) -----
        try:
            from app.services.gwas_scorer import score_gwas
            gwas_results = await score_gwas(
                user_df=user_df_full,
                session=session,
                ancestry_group=ancestry_group,
                genome_build=genome_build,
                user_id=user_id,
                analysis_id=analysis_id,
            )
            if gwas_results:
                log.info(f"[{analysis_id}] Scored {len(gwas_results)} GWAS-hit PRS")
        except Exception as e:
            log.error(f"[{analysis_id}] GWAS scoring failed (non-fatal): {e}")

        # =================================================================
        # STEP 6: Complete
        # =================================================================
        analysis.status = "complete"
        analysis.completed_at = datetime.now(timezone.utc)
        await session.commit()

        elapsed_total = time.perf_counter() - t_total
        log.info(
            f"[{analysis_id}] Analysis fully complete in {elapsed_total:.2f}s "
            f"(fast={elapsed_fast:.2f}s, prs={elapsed_prs:.2f}s)"
        )

    except asyncio.CancelledError:
        log.warning(f"[{analysis_id}] PRS scoring cancelled (server shutting down)")
        await _fail_analysis(
            session, analysis,
            "PRS scoring interrupted by server shutdown.",
            set_failed=False,  # fast results already committed
        )

    except Exception as e:
        log.error(f"[{analysis_id}] PRS scoring failed: {e}", exc_info=True)
        await _fail_analysis(
            session, analysis,
            "PRS scoring failed. Please try again or contact support.",
            set_failed=False,  # fast results already committed
        )
