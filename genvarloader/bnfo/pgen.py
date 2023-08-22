from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import pgenlib
import polars as pl
from numpy.typing import NDArray

from .types import DenseAlleles, Variants


class Pgen(Variants):
    def __init__(
        self, path: Union[str, Path], samples: Optional[List[str]] = None
    ) -> None:
        # pgen is exclusively diploid
        self.ploidy = 2

        path = Path(path)
        self.pgen_path = path

        psam_samples = pl.read_csv(
            path.with_suffix(".psam"), separator="\t", columns=["IID"]
        )["IID"].to_numpy()
        if samples is not None:
            _samples, sample_idx, _ = np.intersect1d(
                psam_samples, samples, return_indices=True
            )
            if len(_samples) == len(samples):
                raise ValueError("Got samples that are not in the pgen file.")
            self.samples = _samples
            self.sample_idx = sample_idx.astype(np.uint32)
        else:
            self.samples = psam_samples
            self.sample_idx = np.arange(len(psam_samples), dtype=np.uint32)
        self.n_samples = len(self.samples)

        pvar = pgenlib.PvarReader(bytes(path.with_suffix(".pvar")))
        variant_ids = [
            pvar.get_variant_id(i).split(b":") for i in range(pvar.get_variant_ct())
        ]
        contigs = pl.Series([v[0] for v in variant_ids]).cast(pl.Utf8).set_sorted()
        offsets = contigs.unique_counts().to_numpy()
        self.contig_idx = {
            c: i for i, c in enumerate(contigs.unique(maintain_order=True))
        }
        # (c+1)
        self.contig_offsets = np.concatenate([np.array([0], dtype="u4"), offsets])
        # (v)
        self.positions = np.asarray([v[1] for v in variant_ids]).astype(np.int32)
        # (v p)
        self.alleles: NDArray[np.bytes_] = np.asarray([v[2:] for v in variant_ids])

    def _pgen(self, samples: Optional[List[str]] = None):
        if samples is not None:
            _samples, sample_idx, _ = np.intersect1d(
                self.samples, samples, return_indices=True
            )
            if len(_samples) == len(samples):
                raise ValueError("Got samples that are not in the pgen file.")
            sample_idx = self.sample_idx[sample_idx]
        else:
            sample_idx = self.sample_idx
        return pgenlib.PgenReader(bytes(self.pgen_path), sample_subset=sample_idx)

    def read(
        self, contig: str, start: int, end: int, **kwargs
    ) -> Optional[DenseAlleles]:
        samples = kwargs.get("samples", None)
        if samples is None:
            n_samples = self.n_samples
        else:
            n_samples = len(samples)

        # get variant positions and indices
        c_idx = self.contig_idx[contig]
        c_slice = slice(self.contig_offsets[c_idx], self.contig_offsets[c_idx + 1])
        positions = self.positions[c_slice]
        s_idx, e_idx = np.searchsorted(positions, [start, end])
        if s_idx == e_idx:
            return
        positions = positions[s_idx:e_idx]

        # get alleles
        with self._pgen(samples) as f:
            # (v s*2)
            genotypes = np.empty(
                (e_idx - s_idx, n_samples * self.ploidy), dtype=np.int32
            )
            f.read_alleles_range(s_idx, e_idx, genotypes)
        genotypes[genotypes == -9] = 0
        # (s*2 v)
        genotypes = genotypes.swapaxes(0, 1)
        # (s 2 v)
        genotypes = np.stack([genotypes[::2], genotypes[1::2]], 1)
        # (s 2 v)
        alleles = self.alleles[np.arange(s_idx, e_idx), genotypes]

        return DenseAlleles(positions, alleles)