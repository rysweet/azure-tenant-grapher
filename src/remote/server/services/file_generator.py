"""
File Generator Service for ATG Remote Operations.

Philosophy:
- Manage output files for operations
- Create ZIP archives for download
- Clean up old files
- Path validation for security

Public API:
    FileGenerator: File generation and management service
"""

import logging
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class FileGenerator:
    """
    Generate and manage output files for ATG operations.

    Handles file storage, ZIP archive creation, and cleanup.

    Attributes:
        output_dir: Base directory for all outputs
    """

    def __init__(self, output_dir: Path = Path("outputs")):
        """
        Initialize file generator.

        Args:
            output_dir: Base directory for outputs (default: outputs/)
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_job_output_dir(self, job_id: str) -> Path:
        """
        Get output directory for a job.

        Args:
            job_id: Job identifier

        Returns:
            Path to job output directory
        """
        job_dir = self.output_dir / job_id
        return job_dir

    def validate_path(self, path: Path) -> Path:
        """
        Validate path is within output directory.

        Prevents path traversal attacks.

        Args:
            path: Path to validate

        Returns:
            Validated absolute path

        Raises:
            ValueError: If path is outside output directory
        """
        resolved = path.resolve()
        base = self.output_dir.resolve()

        try:
            resolved.relative_to(base)
        except ValueError as e:
            raise ValueError(
                f"Path {path} is outside allowed output directory {self.output_dir}"
            ) from e

        return resolved

    def list_files(self, job_id: str) -> List[Path]:
        """
        List all files for a job.

        Args:
            job_id: Job identifier

        Returns:
            List of file paths relative to job directory
        """
        job_dir = self.get_job_output_dir(job_id)

        if not job_dir.exists():
            return []

        # Get all files recursively
        files = [f for f in job_dir.rglob("*") if f.is_file()]
        return files

    def create_zip_archive(
        self, job_id: str, output_path: Optional[Path] = None
    ) -> Path:
        """
        Create ZIP archive of all job files.

        Args:
            job_id: Job identifier
            output_path: Optional custom output path for ZIP

        Returns:
            Path to created ZIP file

        Raises:
            ValueError: If no files found for job
        """
        job_dir = self.get_job_output_dir(job_id)

        if not job_dir.exists():
            raise ValueError(f"No output directory found for job {job_id}")

        files = self.list_files(job_id)
        if not files:
            raise ValueError(f"No files found for job {job_id}")

        # Determine ZIP path
        if output_path:
            zip_path = self.validate_path(output_path)
        else:
            zip_path = self.output_dir / f"{job_id}.zip"

        # Create ZIP archive
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in files:
                # Add file with path relative to job directory
                arcname = file_path.relative_to(job_dir)
                zf.write(file_path, arcname)

        logger.info(
            f"Created ZIP archive for job {job_id}: {zip_path} ({len(files)} files)"
        )
        return zip_path

    def get_file_info(self, job_id: str) -> dict:
        """
        Get information about job output files.

        Args:
            job_id: Job identifier

        Returns:
            Dictionary with file information
        """
        job_dir = self.get_job_output_dir(job_id)

        if not job_dir.exists():
            return {
                "exists": False,
                "file_count": 0,
                "total_size_bytes": 0,
                "directory": str(job_dir),
            }

        files = self.list_files(job_id)
        total_size = sum(f.stat().st_size for f in files)

        return {
            "exists": True,
            "file_count": len(files),
            "total_size_bytes": total_size,
            "directory": str(job_dir),
            "files": [str(f.relative_to(job_dir)) for f in files],
        }

    def cleanup_job_files(self, job_id: str) -> bool:
        """
        Delete all files for a job.

        Args:
            job_id: Job identifier

        Returns:
            True if files were deleted, False if no files existed
        """
        job_dir = self.get_job_output_dir(job_id)

        if not job_dir.exists():
            return False

        # Remove entire job directory
        shutil.rmtree(job_dir)
        logger.info(f"Deleted output files for job {job_id}")

        # Also remove ZIP if exists
        zip_path = self.output_dir / f"{job_id}.zip"
        if zip_path.exists():
            zip_path.unlink()
            logger.info(f"Deleted ZIP archive for job {job_id}")

        return True

    def cleanup_old_files(self, max_age_days: int = 7) -> int:
        """
        Clean up old job outputs.

        Args:
            max_age_days: Maximum age in days (default: 7)

        Returns:
            Number of jobs cleaned up
        """
        import time

        max_age_seconds = max_age_days * 24 * 60 * 60
        current_time = time.time()
        cleanup_count = 0

        for job_dir in self.output_dir.iterdir():
            if not job_dir.is_dir():
                continue

            # Check directory age
            dir_age = current_time - job_dir.stat().st_mtime

            if dir_age > max_age_seconds:
                job_id = job_dir.name
                if self.cleanup_job_files(job_id):
                    cleanup_count += 1

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} old job outputs")

        return cleanup_count


__all__ = ["FileGenerator"]
