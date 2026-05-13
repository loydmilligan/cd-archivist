# Data Model

## Disc

A disc is the top-level archival unit.

Required fields:

- `disc_id`
- `schema_version`
- `created_at`
- `status`

Possible statuses:

- `captured`
- `ripped`
- `paired`
- `metadata_generated`
- `needs_review`
- `accepted`
- `published`
- `error`

## Capture session

A capture session represents one burst of photos.

Fields:

- `capture_id`
- `started_at`
- `ended_at`
- `trigger`
- `camera_device`
- `image_paths`
- `notes`

## Rip session

A rip session represents one completed or attempted CD import.

Fields:

- `rip_id`
- `started_at`
- `ended_at`
- `source_machine`
- `source_path`
- `audio_paths`
- `track_count`
- `format`
- `rip_log_path`
- `status`

## Metadata

Fields:

- `visible_text`
- `probable_title`
- `probable_date`
- `disc_brand`
- `disc_type`
- `handwritten`
- `marker_color`
- `physical_description`
- `confidence`
- `needs_human_review`

## Pairing

Fields:

- `capture_id`
- `rip_id`
- `paired_at`
- `method`
- `confidence`
- `notes`
