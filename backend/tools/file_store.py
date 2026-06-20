"""
File Store - in-memory store for uploaded .NET files and generated Java output.
Keyed by job_id so concurrent migrations are isolated.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FileStore:
    """
    Lightweight in-memory store that maps job_id → filename → content.
    Two separate namespaces:
        _input   - uploaded .NET source files
        _output  - generated Java / pom.xml / application.yml files
    """

    def __init__(self) -> None:
        self._input: Dict[str, Dict[str, str]] = {}
        self._output: Dict[str, Dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def create_job(self, job_id: str) -> None:
        self._input[job_id] = {}
        self._output[job_id] = {}
        logger.info("FileStore: job %s created", job_id)

    def cleanup(self, job_id: str) -> None:
        self._input.pop(job_id, None)
        self._output.pop(job_id, None)
        logger.info("FileStore: job %s cleaned up", job_id)

    # ------------------------------------------------------------------
    # Input (uploaded .NET files)
    # ------------------------------------------------------------------

    def store_input(self, job_id: str, filename: str, content: str) -> None:
        if job_id not in self._input:
            self.create_job(job_id)
        self._input[job_id][filename] = content
        logger.debug("FileStore: stored input '%s' (%d chars) for job %s",
                     filename, len(content), job_id)

    def get_input(self, job_id: str, filename: str) -> Optional[str]:
        return self._input.get(job_id, {}).get(filename)

    def list_inputs(self, job_id: str) -> Dict[str, str]:
        return dict(self._input.get(job_id, {}))

    # ------------------------------------------------------------------
    # Output (generated Java files)
    # ------------------------------------------------------------------

    def store_output(self, job_id: str, filename: str, content: str) -> None:
        if job_id not in self._output:
            self._output[job_id] = {}
        self._output[job_id][filename] = content
        logger.debug("FileStore: stored output '%s' for job %s", filename, job_id)

    def get_output(self, job_id: str, filename: str) -> Optional[str]:
        return self._output.get(job_id, {}).get(filename)

    def list_outputs(self, job_id: str) -> Dict[str, str]:
        return dict(self._output.get(job_id, {}))


# Singleton
file_store = FileStore()
