# Repository Data Boundary

Status: Active governance rule  
Date: 2026-10-28

## Repository visibility
`kernelshock/Manufacturing-Operations-Platform` is currently **public**.

## Rule
Do not commit proprietary FAIC raw operational/manufacturing evidence to this public repository, including:
- Prolowin product-structure PDFs;
- taquillas containing non-public production detail;
- supplier-commercial files;
- internal cost reports;
- production exports with confidential business data;
- credentials/secrets.

## Permitted public-repo evidence
- SHA-256 manifests;
- synthetic/anonymized fixtures;
- schemas/contracts;
- architecture decisions;
- non-sensitive derived statistics;
- test data specifically created for public development.

## Current five-PDF corpus
The files X-1148, X-1149, X-2209, X-6111 and X-7070 remain external working evidence.

Their SHA-256 values are recorded in:
`docs/04-reference/faic-prolowin-samples/SOURCE-MANIFEST.md`

No binary PDF is committed.

## Future option
If source evidence must be versioned, use an approved private repository or protected document store and reference it by immutable identifier/hash from this repository.
