import { useCallback, useState } from "react";

import { readDraft, removeDraft, writeDraft } from "../draftStorage";

/** A composer draft and the two ways it changes: edited, or sent and forgotten. */
export type Draft = {
  text: string;
  setText: (text: string) => void;
  /** Drop the draft and the stored copy with it — what a sent question does. */
  clearText: () => void;
};

/**
 * The text of one composer draft, kept in sync with its stored copy.
 *
 * Owns the text rather than shadowing someone else's state, so there is a single source of
 * truth for what the field holds. Writes are synchronous: a debounce would have to be flushed
 * on unmount to avoid losing the last keystrokes, and a few hundred bytes costs far less than
 * the render already happening around it.
 *
 * Example:
 *     const { text, setText, clearText } = useDraft(conversationId);
 */
export function useDraft(draftKey: string): Draft {
  // Seeded from storage in the initializer, not an effect, so a restored draft is already
  // in place for the first layout pass — the field never paints empty and then jumps.
  const [draft, setDraft] = useState(() => ({ key: draftKey, text: readDraft(draftKey) }));

  // Switching conversations re-points the composer instead of remounting it, so the key
  // changing is the signal to load that conversation's own draft. Adjusting state during
  // render (rather than in an effect) re-renders before paint, so no stale draft is shown.
  if (draft.key !== draftKey) setDraft({ key: draftKey, text: readDraft(draftKey) });

  const setText = useCallback(
    (text: string) => {
      setDraft({ key: draftKey, text });
      writeDraft(draftKey, text);
    },
    [draftKey],
  );

  const clearText = useCallback(() => {
    setDraft({ key: draftKey, text: "" });
    removeDraft(draftKey);
  }, [draftKey]);

  return { text: draft.text, setText, clearText };
}
