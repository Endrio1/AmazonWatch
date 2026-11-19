"""Limpeza dos diretórios de arquivos gerenciados pelo coletor."""

import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def remove_expired_files(directory: Path, patterns: tuple[str, ...], cutoff: datetime) -> int:
    """Remove arquivos antigos por mtime, sem seguir links simbólicos."""
    removed = 0
    for pattern in patterns:
        for path in directory.glob(pattern):
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                if path.stat().st_mtime < cutoff.timestamp():
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                log.exception("Falha ao remover arquivo expirado %s", path)
    return removed
