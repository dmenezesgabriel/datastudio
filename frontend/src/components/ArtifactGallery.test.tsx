import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { ArtifactGallery } from "./ArtifactGallery";
import type { ArtifactSummary } from "../types";

afterEach(cleanup);

const ONE: ArtifactSummary[] = [{ id: "a1", title: "Sales", updatedAt: 0, versionCount: 1 }];

test("gives the populated gallery a heading so the outline doesn't skip a level", () => {
  render(<ArtifactGallery artifacts={ONE} onOpen={vi.fn()} onDelete={vi.fn()} />);
  expect(screen.getByRole("heading", { level: 2, name: /saved dashboards/i })).toBeTruthy();
});

test("does not delete on the first click — it asks to confirm", () => {
  // Deletion is destructive and irreversible; a single mis-click must not destroy saved work.
  const onDelete = vi.fn();
  render(<ArtifactGallery artifacts={ONE} onOpen={vi.fn()} onDelete={onDelete} />);

  fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
  expect(onDelete).not.toHaveBeenCalled();

  // Confirming actually deletes the right artifact.
  fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
  expect(onDelete).toHaveBeenCalledWith("a1");
});

test("lets the user back out of a pending delete", () => {
  const onDelete = vi.fn();
  render(<ArtifactGallery artifacts={ONE} onOpen={vi.fn()} onDelete={onDelete} />);

  fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
  fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

  expect(onDelete).not.toHaveBeenCalled();
  // The card returns to its normal actions.
  expect(screen.getByRole("button", { name: /^delete$/i })).toBeTruthy();
});
