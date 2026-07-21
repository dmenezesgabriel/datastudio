import { type KeyboardEvent, memo, useEffect, useRef, useState } from "react";

// The bottom-docked message composer. A textarea (grows with content, submits on Enter,
// newline on Shift+Enter) plus a send button — the familiar Claude/ChatGPT affordance.
//
// The draft lives here, not in App: keystrokes must not re-render the transcript (each
// would otherwise rebuild every dashboard/chart). App only learns the text on submit.
// memo (with a stable onSubmit) keeps it off the per-streaming-patch re-render path too.
export const Composer = memo(function Composer({
  onSubmit,
  disabled,
  placeholder = "Ask a question about your data…",
  label = "Ask",
  clearSignal,
  autoFocus = false,
}: {
  onSubmit: (prompt: string) => void;
  disabled: boolean;
  placeholder?: string;
  label?: string;
  // Bumped by the parent when a submission has succeeded. Until then the draft is preserved,
  // so a failed send leaves the text in place to retry rather than discarding it (audit MOD-3).
  clearSignal?: number;
  // Land the cursor in the field on mount so the user can type immediately (audit follow-up).
  autoFocus?: boolean;
}) {
  const [value, setValue] = useState("");
  const lastCleared = useRef(clearSignal);

  useEffect(() => {
    if (clearSignal !== lastCleared.current) {
      lastCleared.current = clearSignal;
      setValue("");
    }
  }, [clearSignal]);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    // The draft is NOT cleared here — only a success signal from the parent clears it, so a
    // failed send keeps the question for one retry (audit MOD-3).
    onSubmit(trimmed);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="composer p-4">
      <form
        className="composer__form max-w-content mx-auto flex gap-2 items-end"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <textarea
          // eslint-disable-next-line jsx-a11y/no-autofocus -- opt-in via prop; only the
          // top-level chat composer sets it, where focusing the input on load is expected.
          autoFocus={autoFocus}
          // A placeholder doubles as the field's name only while it's empty — once the user
          // types, the field goes unnamed. An explicit aria-label keeps it named throughout
          // (a11y audit SC 3.3.2 / 4.1.2).
          aria-label={placeholder}
          className="composer__input flex-1 text-base bg-raised border-strong rounded-md p-3"
          rows={1}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
        />
        <button
          type="submit"
          // The visible label collapses to "…" while streaming; a stable aria-label keeps the
          // button's accessible name as the action ("Ask"/"Edit") instead of "dot dot dot".
          aria-label={label}
          aria-busy={disabled}
          className="composer__send px-5 py-3 text-base font-medium rounded-md cursor-pointer"
          disabled={disabled}
        >
          {disabled ? "…" : label}
        </button>
      </form>
    </div>
  );
});
