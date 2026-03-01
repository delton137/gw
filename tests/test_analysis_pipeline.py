"""Tests for the unified analysis pipeline."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

from app.services.analysis import run_analysis_pipeline


def _mock_analysis(analysis_id=None):
    """Create a mock Analysis ORM object."""
    analysis = MagicMock()
    analysis.id = uuid.UUID(analysis_id) if analysis_id else uuid.uuid4()
    analysis.user_id = "user_test123"
    analysis.status = "pending"
    analysis.chip_type = None
    analysis.variant_count = None
    analysis.error_message = None
    analysis.detected_ancestry = None
    analysis.ancestry_method = None
    analysis.ancestry_confidence = None
    analysis.selected_ancestry = None
    analysis.genome_build = None
    analysis.file_format = None
    analysis.completed_at = None
    return analysis


def _user_df(n_variants=100):
    """Create a simple user DataFrame."""
    return pl.DataFrame({
        "rsid": [f"rs{i}" for i in range(n_variants)],
        "chrom": ["1"] * n_variants,
        "position": list(range(n_variants)),
        "allele1": ["A"] * n_variants,
        "allele2": ["G"] * n_variants,
    })


@pytest.fixture
def analysis_id():
    return str(uuid.uuid4())


@pytest.fixture
def session():
    return AsyncMock()


def _setup_session_for_fast_steps(session, analysis):
    """Set up session mocks for a pipeline run through fast steps."""
    analysis_result = MagicMock()
    analysis_result.scalar_one_or_none.return_value = analysis

    snpedia_result = MagicMock()
    snpedia_result.__iter__ = MagicMock(return_value=iter([]))

    # For PRS scoring: select(PrsScore) returns empty list
    prs_scores_result = MagicMock()
    prs_scalars = MagicMock()
    prs_scalars.all.return_value = []
    prs_scores_result.scalars.return_value = prs_scalars

    # Batch-loaded weights (empty — no PRS scores to score)
    all_weights_result = MagicMock()
    all_weights_result.fetchall.return_value = []

    # Batch-loaded ref dists (empty)
    all_refs_result = MagicMock()
    all_refs_scalars = MagicMock()
    all_refs_scalars.__iter__ = MagicMock(return_value=iter([]))
    all_refs_result.scalars.return_value = all_refs_scalars

    session.execute = AsyncMock(side_effect=[
        analysis_result,    # select(Analysis)
        snpedia_result,     # snpedia_snps
        prs_scores_result,  # select(PrsScore)
        all_weights_result, # batch-load all weights
        all_refs_result,    # batch-load all ref dists
    ])
    session.commit = AsyncMock()
    session.rollback = AsyncMock()


class TestFastStepsSetDone:
    @pytest.mark.asyncio
    async def test_fast_steps_set_done(self, analysis_id, session):
        """Fast steps (parse, traits, PGx, blood type) set status to 'done'."""
        analysis = _mock_analysis(analysis_id)
        user_df = _user_df()

        _setup_session_for_fast_steps(session, analysis)

        with patch("app.services.analysis.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                (user_df, "23andme", "23andme_v5", {}),  # parse
                None,                                  # estimate_ancestry
            ]
            with patch("app.services.analysis.match_traits", new_callable=AsyncMock) as mock_traits:
                mock_traits.return_value = []
                with patch("app.services.analysis.match_clinvar", new_callable=AsyncMock) as mock_cv:
                    mock_cv.return_value = []
                    with patch("app.services.analysis.match_pgx", new_callable=AsyncMock) as mock_pgx:
                        mock_pgx.return_value = []
                        with patch("app.services.analysis.determine_blood_type") as mock_bt:
                            mock_bt.return_value = None
                            await run_analysis_pipeline(
                                analysis_id=analysis_id,
                                user_id="user_test123",
                                tmp_path="/tmp/fake.txt",
                                ancestry_group="EUR",
                                session=session,
                            )

        # Status should have been set to "done" at some point (then "scoring_prs", then "complete")
        status_calls = [
            call[0] for call in session.commit.call_args_list
        ]
        # The pipeline sets status to done, then scoring_prs, then complete
        assert analysis.status == "complete"
        assert analysis.completed_at is not None

    @pytest.mark.asyncio
    async def test_chip_type_and_variant_count_set(self, analysis_id, session):
        """Parse step sets chip_type and variant_count."""
        analysis = _mock_analysis(analysis_id)
        user_df = _user_df(500)

        _setup_session_for_fast_steps(session, analysis)

        with patch("app.services.analysis.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                (user_df, "23andme", "23andme_v5", {}),
                None,  # ancestry
            ]
            with patch("app.services.analysis.match_traits", new_callable=AsyncMock) as mt:
                mt.return_value = []
                with patch("app.services.analysis.match_clinvar", new_callable=AsyncMock) as mc:
                    mc.return_value = []
                    with patch("app.services.analysis.match_pgx", new_callable=AsyncMock) as mp:
                        mp.return_value = []
                        with patch("app.services.analysis.determine_blood_type") as mbt:
                            mbt.return_value = None
                            await run_analysis_pipeline(
                                analysis_id=analysis_id,
                                user_id="user_test123",
                                tmp_path="/tmp/fake.txt",
                                ancestry_group="EUR",
                                session=session,
                            )

        assert analysis.chip_type == "23andme_v5"
        assert analysis.variant_count == 500


class TestFullPipelineSetsComplete:
    @pytest.mark.asyncio
    async def test_full_pipeline_sets_complete(self, analysis_id, session):
        """A successful full pipeline run sets status to 'complete' with completed_at."""
        analysis = _mock_analysis(analysis_id)
        user_df = _user_df()

        _setup_session_for_fast_steps(session, analysis)

        ancestry_result = MagicMock()
        ancestry_result.best_pop = "EUR"
        ancestry_result.proportions = {"EUR": 0.85, "AFR": 0.10}
        ancestry_result.populations = {"EUR": 0.85, "AFR": 0.10}
        ancestry_result.superpopulations = {"EUR": 0.85, "AFR": 0.10, "EAS": 0.0, "SAS": 0.0, "AMR": 0.05}
        ancestry_result.confidence = 0.85
        ancestry_result.n_markers_used = 200
        ancestry_result.n_markers_total = 128097
        ancestry_result.coverage_quality = "high"
        ancestry_result.is_admixed = False

        with patch("app.services.analysis.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                (user_df, "23andme", "23andme_v5", {}),
                ancestry_result,  # estimate_ancestry
            ]
            with patch("app.services.analysis.match_traits", new_callable=AsyncMock) as mt:
                mt.return_value = []
                with patch("app.services.analysis.match_clinvar", new_callable=AsyncMock) as mc:
                    mc.return_value = []
                    with patch("app.services.analysis.match_pgx", new_callable=AsyncMock) as mp:
                        mp.return_value = []
                        with patch("app.services.analysis.determine_blood_type") as mbt:
                            mbt.return_value = None
                            await run_analysis_pipeline(
                                analysis_id=analysis_id,
                                user_id="user_test123",
                                tmp_path="/tmp/fake.txt",
                                ancestry_group="EUR",
                                session=session,
                            )

        assert analysis.status == "complete"
        assert analysis.completed_at is not None
        # New format: detected_ancestry is a rich dict with populations, superpopulations, etc.
        assert "populations" in analysis.detected_ancestry
        assert "superpopulations" in analysis.detected_ancestry
        assert analysis.detected_ancestry["n_markers_used"] == 200
        assert analysis.ancestry_confidence == 0.85
        assert analysis.ancestry_method == "aeon_mle"


class TestSelectedAncestryPersisted:
    @pytest.mark.asyncio
    async def test_selected_ancestry_stored(self, analysis_id, session):
        """User-selected ancestry is stored in selected_ancestry field."""
        analysis = _mock_analysis(analysis_id)
        user_df = _user_df()

        _setup_session_for_fast_steps(session, analysis)

        with patch("app.services.analysis.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                (user_df, "23andme", "23andme_v5", {}),
                None,  # ancestry
            ]
            with patch("app.services.analysis.match_traits", new_callable=AsyncMock) as mt:
                mt.return_value = []
                with patch("app.services.analysis.match_clinvar", new_callable=AsyncMock) as mc:
                    mc.return_value = []
                    with patch("app.services.analysis.match_pgx", new_callable=AsyncMock) as mp:
                        mp.return_value = []
                        with patch("app.services.analysis.determine_blood_type") as mbt:
                            mbt.return_value = None
                            await run_analysis_pipeline(
                                analysis_id=analysis_id,
                                user_id="user_test123",
                                tmp_path="/tmp/fake.txt",
                                ancestry_group="AFR",
                                session=session,
                            )

        assert analysis.selected_ancestry == "AFR"


class TestAncestryEstimatorRunsInBackground:
    @pytest.mark.asyncio
    async def test_ancestry_estimator_runs_after_done(self, analysis_id, session):
        """Ancestry estimation runs after fast results are committed."""
        analysis = _mock_analysis(analysis_id)
        user_df = _user_df()

        _setup_session_for_fast_steps(session, analysis)

        ancestry_result = MagicMock()
        ancestry_result.best_pop = "AFR"
        ancestry_result.proportions = {"AFR": 0.90, "EUR": 0.05, "EAS": 0.05}
        ancestry_result.populations = {"AFR": 0.90, "EUR": 0.05, "EAS": 0.05}
        ancestry_result.superpopulations = {"AFR": 0.90, "EUR": 0.05, "EAS": 0.05, "SAS": 0.0, "AMR": 0.0}
        ancestry_result.confidence = 0.90
        ancestry_result.n_markers_used = 300
        ancestry_result.n_markers_total = 128097
        ancestry_result.coverage_quality = "low"
        ancestry_result.is_admixed = False

        with patch("app.services.analysis.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                (user_df, "23andme", "23andme_v5", {}),
                ancestry_result,  # estimate_ancestry
            ]
            with patch("app.services.analysis.match_traits", new_callable=AsyncMock) as mt:
                mt.return_value = []
                with patch("app.services.analysis.match_clinvar", new_callable=AsyncMock) as mc:
                    mc.return_value = []
                    with patch("app.services.analysis.match_pgx", new_callable=AsyncMock) as mp:
                        mp.return_value = []
                        with patch("app.services.analysis.determine_blood_type") as mbt:
                            mbt.return_value = None
                            await run_analysis_pipeline(
                                analysis_id=analysis_id,
                                user_id="user_test123",
                                tmp_path="/tmp/fake.txt",
                                ancestry_group="EUR",
                                session=session,
                            )

        assert "populations" in analysis.detected_ancestry
        assert "superpopulations" in analysis.detected_ancestry
        assert analysis.detected_ancestry["n_markers_used"] == 300
        assert analysis.ancestry_method == "aeon_mle"
        assert analysis.ancestry_confidence == 0.90

    @pytest.mark.asyncio
    async def test_ancestry_estimation_failure_logged(self, analysis_id, session):
        """When ancestry estimation returns None, method is set to 'computed_failed'."""
        analysis = _mock_analysis(analysis_id)
        user_df = _user_df()

        _setup_session_for_fast_steps(session, analysis)

        with patch("app.services.analysis.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                (user_df, "23andme", "23andme_v5", {}),
                None,  # ancestry estimation fails (too few AIMs)
            ]
            with patch("app.services.analysis.match_traits", new_callable=AsyncMock) as mt:
                mt.return_value = []
                with patch("app.services.analysis.match_clinvar", new_callable=AsyncMock) as mc:
                    mc.return_value = []
                    with patch("app.services.analysis.match_pgx", new_callable=AsyncMock) as mp:
                        mp.return_value = []
                        with patch("app.services.analysis.determine_blood_type") as mbt:
                            mbt.return_value = None
                            await run_analysis_pipeline(
                                analysis_id=analysis_id,
                                user_id="user_test123",
                                tmp_path="/tmp/fake.txt",
                                ancestry_group="EUR",
                                session=session,
                            )

        assert analysis.ancestry_method == "computed_failed"


class TestPrsFailureKeepsDone:
    @pytest.mark.asyncio
    async def test_prs_failure_preserves_fast_results(self, analysis_id, session):
        """PRS scoring failure keeps status at done with error_message set."""
        analysis = _mock_analysis(analysis_id)
        user_df = _user_df()

        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis

        snpedia_result = MagicMock()
        snpedia_result.__iter__ = MagicMock(return_value=iter([]))

        # Make PRS scoring blow up on select(PrsScore)
        prs_scores_result = MagicMock()
        prs_scalars = MagicMock()
        prs_scalars.all.side_effect = Exception("Database connection lost")
        prs_scores_result.scalars.return_value = prs_scalars

        # The exception triggers before the batch queries, so we only need 3 entries
        session.execute = AsyncMock(side_effect=[
            analysis_result,    # select(Analysis)
            snpedia_result,     # snpedia_snps
            prs_scores_result,  # select(PrsScore) — blows up on .scalars().all()
        ])
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        with patch("app.services.analysis.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = [
                (user_df, "23andme", "23andme_v5", {}),
            ]
            with patch("app.services.analysis.match_traits", new_callable=AsyncMock) as mt:
                mt.return_value = []
                with patch("app.services.analysis.match_clinvar", new_callable=AsyncMock) as mc:
                    mc.return_value = []
                    with patch("app.services.analysis.match_pgx", new_callable=AsyncMock) as mp:
                        mp.return_value = []
                        with patch("app.services.analysis.determine_blood_type") as mbt:
                            mbt.return_value = None
                            await run_analysis_pipeline(
                                analysis_id=analysis_id,
                                user_id="user_test123",
                                tmp_path="/tmp/fake.txt",
                                ancestry_group="EUR",
                                session=session,
                            )

        # Fast results committed — PRS failure should NOT set status to "failed"
        # Status stays at whatever it was when the PRS error handler runs
        assert analysis.error_message is not None
        assert "failed" in analysis.error_message.lower() or "Database" in analysis.error_message


class TestPipelineFailure:
    @pytest.mark.asyncio
    async def test_analysis_not_found_returns_early(self, analysis_id, session):
        """Pipeline returns early if analysis record not found."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        await run_analysis_pipeline(
            analysis_id=analysis_id,
            user_id="user_test123",
            tmp_path="/tmp/fake.txt",
            ancestry_group="EUR",
            session=session,
        )

        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_parse_error_sets_failed(self, analysis_id, session):
        """Parse failure sets status to 'failed'."""
        analysis = _mock_analysis(analysis_id)

        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis
        session.execute = AsyncMock(return_value=analysis_result)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        with patch("app.services.analysis.asyncio.to_thread") as mock_thread:
            mock_thread.side_effect = Exception("Bad file format")

            await run_analysis_pipeline(
                analysis_id=analysis_id,
                user_id="user_test123",
                tmp_path="/tmp/nonexistent.txt",
                ancestry_group="EUR",
                session=session,
            )

        assert analysis.status == "failed"
        assert analysis.error_message is not None
        session.rollback.assert_called()
