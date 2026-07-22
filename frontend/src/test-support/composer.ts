import { act, fireEvent, screen } from "@testing-library/react";

// Driving the chat composer from a test. The chat surface is a ProseMirror editor rather
// than a textarea, so a question cannot be set with fireEvent.change — it goes in the way a
// browser puts it in, and the editor is told the DOM changed. One helper, because every
// suite that asks a question needs exactly this.

/**
 * Type `question` into the chat composer and send it.
 *
 * Example:
 *     await askQuestion("Revenue by month");
 *     expect(pathname()).toMatch(/^\/chat\//);
 */
export async function askQuestion(question: string): Promise<void> {
  const field = screen.getByRole("textbox", { name: /Ask a question/i });
  // Awaited: ProseMirror learns about DOM edits through a MutationObserver, whose records
  // only arrive on the next microtask — asserting before that sees an empty draft.
  await act(async () => {
    field.focus();
    const paragraph = field.querySelector("p") ?? field;
    paragraph.textContent = question;
    fireEvent.input(field);
    await Promise.resolve();
  });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));
  });
}
