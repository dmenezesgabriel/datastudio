// Unsent composer drafts, parked in localStorage so navigating away or reloading the tab
// does not throw away a half-written question.
//
// Every call is wrapped: localStorage throws outright in Safari's private mode and when the
// quota is full, and a composer that cannot store a draft must still let you type one. The
// whole feature degrades to "drafts don't survive a reload" rather than breaking the input.

// Namespaced and versioned. The version is how a change of stored shape retires the old
// drafts: bump it and the previous keys are simply never read again.
const DRAFT_KEY_PREFIX = "datastudio.draft.v1.";

/**
 * Read the draft parked under `draftKey`, or "" when there is none.
 *
 * Example:
 *     const text = readDraft("c-1"); // "revenue by mont"
 */
export function readDraft(draftKey: string): string {
  try {
    return window.localStorage.getItem(DRAFT_KEY_PREFIX + draftKey) ?? "";
  } catch {
    return ""; // storage denied — behave as though nothing was ever saved
  }
}

/**
 * Park `text` as the draft for `draftKey`, or drop the entry when it is empty.
 *
 * Example:
 *     writeDraft("c-1", "revenue by mont");
 */
export function writeDraft(draftKey: string, text: string): void {
  if (text === "") return removeDraft(draftKey);
  try {
    window.localStorage.setItem(DRAFT_KEY_PREFIX + draftKey, text);
  } catch {
    // Storage denied or full: the draft just will not outlive this view.
  }
}

/**
 * Forget the draft for `draftKey` — what sending the question does.
 *
 * Example:
 *     removeDraft("c-1");
 */
export function removeDraft(draftKey: string): void {
  try {
    window.localStorage.removeItem(DRAFT_KEY_PREFIX + draftKey);
  } catch {
    // Nothing to do: an unremovable entry is still overwritten by the next write.
  }
}
