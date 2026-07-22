import {
  type KeyboardEvent,
  type RefObject,
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

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
  restoreSignal,
  autoFocus = false,
}: {
  onSubmit: (prompt: string) => void;
  disabled: boolean;
  placeholder?: string;
  label?: string;
  // Bumped by the parent when the last send failed. The draft is cleared optimistically on
  // submit; a bump restores the just-sent text so a single retry re-sends it (audit MOD-3).
  restoreSignal?: number;
  // Land the cursor in the field on mount so the user can type immediately (audit follow-up).
  autoFocus?: boolean;
}) {
  const [value, setValue] = useState("");
  const field = useAutoGrow(value);
  const lastSubmitted = useRef("");
  const lastRestore = useRef(restoreSignal);

  useEffect(() => {
    if (restoreSignal !== lastRestore.current) {
      lastRestore.current = restoreSignal;
      setValue(lastSubmitted.current); // the send failed → put the question back for retry
    }
  }, [restoreSignal]);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    lastSubmitted.current = trimmed;
    onSubmit(trimmed);
    setValue(""); // clear optimistically; restored via restoreSignal only if the send fails
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
          ref={field}
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

// Sizes the field to the draft it holds, so a long question is never scrolled out of its
// own view and a Shift+Enter newline is visible. The height resets before each measurement
// — scrollHeight only ever reports the content's full extent, so without the reset the
// field would ratchet upward and never shrink. The ceiling is CSS (.composer__input's
// max-height), which clamps whatever this asks for.
function useAutoGrow(value: string): RefObject<HTMLTextAreaElement | null> {
  const field = useRef<HTMLTextAreaElement>(null);

  const fitToDraft = useCallback(() => {
    const textarea = field.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    // scrollHeight covers content and padding but not borders, and the field is border-box —
    // sized to scrollHeight alone it sits 2px short of its own text and scrolls at every height.
    const borders = textarea.offsetHeight - textarea.clientHeight;
    textarea.style.height = `${textarea.scrollHeight + borders}px`;
  }, []);

  // Layout effect, not effect: the resize lands in the same paint as the keystroke that
  // caused it, so the field never flashes at the previous draft's height.
  useLayoutEffect(fitToDraft, [value, fitToDraft]);

  // A height is only valid at the width it was measured at — narrow the window, or open a
  // phone keyboard, and a draft measured wide re-wraps taller than the height it is stuck
  // at, hiding its own last lines. Re-measuring settles in one extra pass: the second
  // callback asks for the height already set, and an unchanged box stops the observer.
  useLayoutEffect(() => {
    const textarea = field.current;
    if (!textarea) return;
    const observer = new ResizeObserver(fitToDraft);
    observer.observe(textarea);
    return () => observer.disconnect();
  }, [fitToDraft]);

  return field;
}
