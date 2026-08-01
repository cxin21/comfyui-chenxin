# dictionary/ — in-skill tag dictionary

Sources:

- `danbooru.csv` — 140,782 rows from [Danbooru](https://danbooru.donmai.us/wiki_pages/help:tags) (jsDelivr CDN mirror).
- `wd14-tags.csv` — 10,862 rows from [SmilingWolf/wd-v1-4-tags](https://huggingface.co/SmilingWolf/wd-v1-4-tags) (hf-mirror).
- `tag-index.json` — precomputed index (built by `python internals/build_tag_index.py`).

## Update flow

```bash
python internals/build_tag_index.py        # rebuild index from CSV
python internals/build_tag_index.py --check   # CI: exit 1 if CSV newer
```

## License

Danbooru tags are released under the [Danbooru Terms of Service](https://danbooru.donmai.us/wiki_pages/help:tags) for non-commercial use with attribution. WD14 tags are released by SmilingWolf under the [CreativeML Open RAIL-M license](https://huggingface.co/SmilingWolf/wd-v1-4-tags). See `../LICENSE` for this skill's MIT terms.
