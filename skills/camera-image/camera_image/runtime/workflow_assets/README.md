# Fixed workflow assets

The JSON files in this directory are the execution assets for the production
stages. They are synchronized from the local ComfyUI instance during release,
then loaded from this directory at runtime. The live ComfyUI workflow library
is discovery evidence only; it is never the runtime configuration source.

Each asset must be accompanied by a manifest entry, a profile fingerprint and
an API graph hash. A missing asset or a fingerprint mismatch is fail-closed.

