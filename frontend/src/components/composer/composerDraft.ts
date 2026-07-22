import { type Node as ProseMirrorNode } from "prosemirror-model";

import { composerSchema, docFromText } from "./composerSchema";

// A draft is a document, but what leaves the composer is text: the model is sent a question,
// not markup. Flattening happens here, in one place, so every path out (sending, measuring
// whether there is anything to send) agrees on what the draft says.

/**
 * The text a draft sends — chips flattened to the identifiers they stand for.
 *
 * Example:
 *     draftToText(doc); // "rows in events last month"
 */
export function draftToText(doc: ProseMirrorNode): string {
  // Blocks join with a blank line; leaf nodes (chips, line breaks) supply their own text via
  // the schema's leafText, which textBetween falls back to when given no override.
  return doc.textBetween(0, doc.content.size, "\n\n");
}

/**
 * Restore a stored draft, tolerating one written before drafts were documents.
 *
 * Drafts parked by the previous plain-text composer are still sitting in storage; reading
 * them as text rather than discarding them keeps a half-written question across the upgrade.
 *
 * Example:
 *     draftFromStorage('{"type":"doc",...}')  // the document, chips intact
 *     draftFromStorage("revenue by month")    // one paragraph of plain text
 */
export function draftFromStorage(stored: string): ProseMirrorNode {
  if (stored === "") return docFromText("");
  try {
    return composerSchema.nodeFromJSON(JSON.parse(stored));
  } catch {
    return docFromText(stored); // not a document — an older plain-text draft, or corrupt
  }
}

/**
 * Serialize a draft for storage, keeping chips as chips.
 *
 * Example:
 *     draftToStorage(doc); // '{"type":"doc","content":[...]}'
 */
export function draftToStorage(doc: ProseMirrorNode): string {
  return JSON.stringify(doc.toJSON());
}
