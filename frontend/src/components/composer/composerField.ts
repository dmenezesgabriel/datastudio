/**
 * What the composer shell needs from whichever editing surface is inside it.
 *
 * The shell owns the chrome and the decision to send; a field owns the draft, how that draft
 * is stored, and how it is edited. Keeping the two apart is what lets a field that
 * understands table chips stand in for a plain one without the shell knowing the difference.
 */
export type ComposerFieldHandle = {
  /** The plain text this draft would send — chips flattened to their identifiers. */
  readText: () => string;
  /** Drop the draft and its stored copy: the question has gone. */
  clear: () => void;
  /** Put text back into an emptied field after a send failed (audit MOD-3). */
  restore: (text: string) => void;
};
