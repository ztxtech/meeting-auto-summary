# AI Provider Extension Point

The current web console runs the local transcription skill and builds copy-ready AI context from generated files.

Future provider integrations should live in this directory and expose a small interface:

```js
export async function summarize({ mediaPath, artifacts, outputLanguage }) {}
export async function translate({ artifactPath, targetLanguage }) {}
```

Keep provider credentials outside the repository, preferably in environment variables or files under `.meeting-auto-summary/`.
