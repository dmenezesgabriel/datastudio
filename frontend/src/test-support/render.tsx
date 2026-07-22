import { render } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigationType } from "react-router-dom";

import { App } from "../App";

// Mounts the app at a URL, the way a deep link arrives. `App` deliberately contains no
// Router (main.tsx supplies BrowserRouter) so tests can drive it from a memory history.

/**
 * Render the app as if the browser had just loaded `path`.
 *
 * Example:
 *     renderAt("/chat/past-1");
 *     expect(await screen.findByText("Past answer.")).toBeTruthy();
 */
export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <LocationProbe />
    </MemoryRouter>,
  );
}

/** Reads back the current URL and how we got there, so tests can assert push vs. replace. */
function LocationProbe() {
  const { pathname } = useLocation();
  return (
    <>
      <span data-testid="pathname">{pathname}</span>
      <span data-testid="navigation-type">{useNavigationType()}</span>
    </>
  );
}
