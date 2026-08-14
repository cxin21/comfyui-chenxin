# Troubleshooting

If validation fails, inspect the `errors` returned by `validate_config`.
Image stages require positive/negative prompt strings; video stages require a
single `prompt.text` string. Runtime failures are reported by `run_skill` with
an `error_category` of `input`, `engine_build`, or `comfyui_runtime`.
