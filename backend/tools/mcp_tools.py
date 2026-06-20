"""
MCP Tools - implements the three MCP tool contracts used by the migration agent.
  • read_file   - read an uploaded .NET file by name
  • write_file  - write a generated Java file to output
  • search_code - regex search across all uploaded files
"""
import re
import logging
from typing import Any, Dict, List, Optional

from .file_store import file_store

logger = logging.getLogger(__name__)


class MCPTools:
    """
    Scoped to a single migration job (job_id).
    The agent receives an MCPTools instance and calls these methods
    during analysis and conversion.
    """

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    # ------------------------------------------------------------------
    # read_file
    # ------------------------------------------------------------------

    def read_file(self, filename: str) -> Optional[str]:
        """
        Read an uploaded .NET file from the job's input namespace.
        Returns None if the file does not exist.
        """
        content = file_store.get_input(self.job_id, filename)
        if content is None:
            logger.warning("MCP read_file: '%s' not found in job %s", filename, self.job_id)
        return content

    # ------------------------------------------------------------------
    # write_file
    # ------------------------------------------------------------------

    def write_file(self, filename: str, content: str) -> bool:
        """
        Write a generated Java (or config) file to the job's output namespace.
        Returns True on success.
        """
        file_store.store_output(self.job_id, filename, content)
        logger.info("MCP write_file: '%s' stored for job %s", filename, self.job_id)
        return True

    # ------------------------------------------------------------------
    # search_code
    # ------------------------------------------------------------------

    def search_code(
        self,
        query: str,
        case_insensitive: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search for a regex pattern across all uploaded files for this job.
        Returns a list of match records:
            [{filename, matches: [{line_number, line}], total_matches}]
        """
        results: List[Dict[str, Any]] = []
        flags = re.IGNORECASE if case_insensitive else 0

        for filename, content in file_store.list_inputs(self.job_id).items():
            try:
                found: List[Dict[str, Any]] = []
                for lineno, line in enumerate(content.splitlines(), start=1):
                    if re.search(query, line, flags):
                        found.append({"line_number": lineno, "line": line.strip()})
                if found:
                    results.append(
                        {
                            "filename": filename,
                            "matches": found,
                            "total_matches": len(found),
                        }
                    )
            except re.error as exc:
                logger.error("MCP search_code: bad regex '%s': %s", query, exc)

        return results

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def list_files(self) -> List[str]:
        """List all filenames uploaded for this job."""
        return list(file_store.list_inputs(self.job_id).keys())

    def get_all_content(self) -> Dict[str, str]:
        """Return all uploaded file contents as {filename: content}."""
        return file_store.list_inputs(self.job_id)
