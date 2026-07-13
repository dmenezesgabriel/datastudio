import { type KeyboardEvent, memo, useState } from "react";

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
}: {
  onSubmit: (prompt: string) => void;
  disabled: boolean;
  placeholder?: string;
  label?: string;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
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
          className="composer__input flex-1 text-base bg-raised border-strong rounded-md p-3"
          rows={1}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
        />
        <button
          type="submit"
          className="composer__send px-5 py-3 text-base font-medium rounded-md cursor-pointer"
          disabled={disabled}
        >
          {disabled ? "…" : label}
        </button>
      </form>
    </div>
  );
});
