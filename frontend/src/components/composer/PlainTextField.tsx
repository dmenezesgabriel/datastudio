import {
  type KeyboardEvent,
  type RefObject,
  useCallback,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
} from "react";

import { useDraft } from "../../hooks/useDraft";
import type { ComposerFieldHandle } from "./composerField";

// The composer's plain editing surface: a textarea that grows with its draft. What a
// question needs when nothing in it has to be structured — the dashboard editor, where the
// instruction is prose about the dashboard on screen rather than a reference to the schema.
export function PlainTextField({
  ref,
  draftKey,
  placeholder,
  autoFocus,
  onEnter,
}: {
  ref: RefObject<ComposerFieldHandle | null>;
  draftKey: string;
  placeholder: string;
  autoFocus: boolean;
  /** Enter pressed on a draft that should be sent — the shell decides what that means. */
  onEnter: () => void;
}) {
  const { text, setText, clearText } = useDraft(draftKey);
  const field = useAutoGrow(text);

  useImperativeHandle(
    ref,
    () => ({ readText: () => text, clear: clearText, restore: setText }),
    [text, clearText, setText],
  );

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // While an IME is composing, Enter accepts the candidate it is offering rather than
    // ending the message — sending here would fire mid-word for anyone typing Japanese,
    // Chinese, or Korean. The browser distinguishes the two on the native event, which is
    // what claude.ai and ChatGPT both guard every Enter handler on.
    if (event.nativeEvent.isComposing) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onEnter();
    }
  }

  return (
    <textarea
      ref={field}
      // eslint-disable-next-line jsx-a11y/no-autofocus -- opt-in via prop; only the
      // top-level chat composer sets it, where focusing the input on load is expected.
      autoFocus={autoFocus}
      // A placeholder doubles as the field's name only while it's empty — once the user
      // types, the field goes unnamed. An explicit aria-label keeps it named throughout
      // (a11y audit SC 3.3.2 / 4.1.2).
      aria-label={placeholder}
      className="composer__input w-full text-base p-3"
      rows={1}
      value={text}
      onChange={(event) => setText(event.target.value)}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
    />
  );
}

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
    // scrollHeight covers content and padding but not borders. The border belongs to
    // .composer__box rather than the field, so this measures zero today — measuring it
    // anyway keeps the field correctly sized if it ever regains one of its own.
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
