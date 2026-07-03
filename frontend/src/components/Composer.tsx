import { type KeyboardEvent } from "react";

// The bottom-docked message composer. A textarea (grows with content, submits on Enter,
// newline on Shift+Enter) plus a send button — the familiar Claude/ChatGPT affordance.
export function Composer({
  value,
  onChange,
  onSubmit,
  disabled,
}: {
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  disabled: boolean;
}) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="composer p-4">
      <form
        className="composer__form max-w-content mx-auto flex gap-2 items-end"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <textarea
          className="composer__input flex-1 text-base bg-raised border-strong rounded-md p-3"
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your data…"
        />
        <button
          type="submit"
          className="composer__send px-5 py-3 text-base font-medium rounded-md cursor-pointer"
          disabled={disabled}
        >
          {disabled ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
