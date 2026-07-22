import { memo, useEffect, useRef } from "react";

import { MentionField } from "./composer/MentionField";
import { PlainTextField } from "./composer/PlainTextField";
import type { ComposerFieldHandle } from "./composer/composerField";

// The bottom-docked message composer — the familiar Claude/ChatGPT affordance: an editing
// surface and its send button sharing one bordered box, Enter to send, Shift+Enter for a
// new line.
//
// This is the shell. It owns the chrome and the decision to send; the field inside owns the
// draft, how that draft is stored, and how it is edited. That seam is what lets a field
// which understands table chips stand in for a plain one without changing anything here.
//
// The draft lives in the field, not in App: keystrokes must not re-render the transcript
// (each would otherwise rebuild every dashboard/chart). App only learns the text on submit.
// memo (with a stable onSubmit) keeps it off the per-streaming-patch re-render path too.
export const Composer = memo(function Composer({
  onSubmit,
  disabled,
  draftKey,
  placeholder = "Ask a question about your data…",
  label = "Ask",
  restoreSignal,
  autoFocus = false,
  mentionsEnabled = false,
}: {
  onSubmit: (prompt: string) => void;
  disabled: boolean;
  // Which draft this composer is editing — a conversation id, or an artifact's. Drafts are
  // stored per key, so switching threads shows that thread's own unsent question.
  draftKey: string;
  placeholder?: string;
  label?: string;
  // Bumped by the parent when the last send failed. The draft is cleared optimistically on
  // submit; a bump restores the just-sent text so a single retry re-sends it (audit MOD-3).
  restoreSignal?: number;
  // Land the cursor in the field on mount so the user can type immediately (audit follow-up).
  autoFocus?: boolean;
  // Let "@" reference tables from the connected dataset. Chat asks about the schema, so it
  // opts in; the dashboard editor takes prose about what is already on screen, so it does not.
  mentionsEnabled?: boolean;
}) {
  const field = useRef<ComposerFieldHandle>(null);
  const lastSubmitted = useRef("");
  const lastRestore = useRef(restoreSignal);

  useEffect(() => {
    if (restoreSignal !== lastRestore.current) {
      lastRestore.current = restoreSignal;
      field.current?.restore(lastSubmitted.current); // send failed → put the question back
    }
  }, [restoreSignal]);

  function submit() {
    const trimmed = field.current?.readText().trim() ?? "";
    if (!trimmed || disabled) return;
    lastSubmitted.current = trimmed;
    onSubmit(trimmed);
    field.current?.clear(); // clear optimistically; restored via restoreSignal if it fails
  }

  return (
    <div className="composer p-4">
      <form
        className="composer__form max-w-content mx-auto"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        {/* The field and its send button share one bordered surface, so the pair reads as a
            single control (the shape both claude.ai and ChatGPT use). The border and the
            focus ring belong to this box, not to the field inside it. */}
        <div className="composer__box">
          {mentionsEnabled ? (
            <MentionField
              ref={field}
              draftKey={draftKey}
              placeholder={placeholder}
              autoFocus={autoFocus}
              onEnter={submit}
            />
          ) : (
            <PlainTextField
              ref={field}
              draftKey={draftKey}
              placeholder={placeholder}
              autoFocus={autoFocus}
              onEnter={submit}
            />
          )}
          <div className="composer__actions">
            <button
              type="submit"
              // The visible label collapses to "…" while streaming; a stable aria-label keeps
              // the button's accessible name as the action ("Ask"/"Edit"), not "dot dot dot".
              aria-label={label}
              aria-busy={disabled}
              className="composer__send px-4 py-2 text-base font-medium rounded-md cursor-pointer"
              disabled={disabled}
            >
              {disabled ? "…" : label}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
});
