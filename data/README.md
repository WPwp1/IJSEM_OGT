# Data Files

This folder currently contains **extraction outputs only**.

It does **not** yet contain:

- the final merged temperature database
- external database integration results
- strict no-conflict analysis tables

## Files

### `ijsem_llm_extracted_microbe_records.csv`

This is the main structured extraction table produced from IJSEM markdown plus LLM-based information extraction.

- rows: 16,671
- columns: 54
- scope: one extracted microbial record per row when identifiable from the article text

Key fields include:

- article metadata: `doi`, `title`, `year`, `volume`, `issue`, `url`, `article_type`
- microbial identity: `species_name`, `taxon_rank`, `type_strain`, `strains`
- ecology: `isolation_source`, `isolation_location`
- temperature: JSON-derived, markdown-derived, and final normalized `Tmin`, `Topt`, `Tmax`
- pH: `ph_min`, `ph_opt`, `ph_max`
- salinity: `nacl_min`, `nacl_opt`, `nacl_max`
- phenotype: `oxygen_preference`, `gram_stain`, `cell_morphology`, `motility`, `spore_formation`, `colony_pigmentation`
- molecular and accession fields: `gc_content`, `genome_accessions`, `rrna_accessions`, `bioproject_accessions`, `biosample_accessions`
- provenance and quality control: `evidence`, `temperature_source`, `informative_field_count`, `evidence_count`, `record_status`, `record_reason`

This file is the best representation of the breadth of information extracted by our workflow.

### `ijsem_pdf_extracted_temperature_records.csv`

This is a lighter PDF-derived temperature extraction table.

- rows: 11,700
- columns: 10

It focuses on:

- `species_name`
- `source_file`
- combined temperature text
- parsed `Tmin`, `Topt`, and `Tmax`

This file is useful as an independent temperature-oriented extraction layer, but it contains much less phenotype context than the LLM-derived table above.

## Release Scope

The purpose of this folder is to share what we extracted from the literature before final integration.

For now, we intentionally keep this release focused on extracted information only:

- no merged cross-source database
- no external TMPURA merge
- no final analysis-ready master table

Those later-stage products belong to a different validation and integration step.
