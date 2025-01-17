# GenVarLoader
GenVarLoader provides a fast, memory efficient data loader for training sequence models on genetic variation. For example, this can be used to train a DNA language model on human genetic variation (e.g. [Nucleotide Transformer](https://www.biorxiv.org/content/10.1101/2023.01.11.523679)).

## Features
- Respects memory budget
- Supports insertions and deletions
- Scales to 100,000s of individuals
- Fast!
- Extensible to new file formats (drop a feature request!)
- Coming soon: re-aligning tracks (e.g. expression, chromatin accessibility) to genetic variation (e.g. [BigRNA](https://www.biorxiv.org/content/10.1101/2023.09.20.558508))

## Installation
`pip install genvarloader`

A PyTorch dependency is not included since it requires [special instructions](https://pytorch.org/get-started/locally/).

## Quick Start

```python
import genvarloader as gvl

ref_fasta = 'reference.fasta'
variants = 'variants.pgen' # highly recommended to convert VCFs to PGEN
regions_of_interest = 'regions.bed'
```

Create readers for each file providing sequence data:

```python
ref = gvl.Fasta(name='ref', path=ref_fasta, pad='N')
var = gvl.Pgen(variants)
varseq = gvl.FastaVariants(name='varseq', reference=ref, variants=var)
```

Put them together and get a `torch.DataLoader`:

```python
gvloader = gvl.GVL(
    readers=varseq,
    bed=regions_of_interest,
    fixed_length=1000,
    batch_size=16,
    max_memory_gb=8,
    batch_dims=['sample', 'ploid'],
    shuffle=True,
)

dataloader = gvloader.torch_dataloader()

```

And now you're ready to use the `dataloader` however you need to:

```python
# implement your training loop
for batch in dataloader:
    ...
```