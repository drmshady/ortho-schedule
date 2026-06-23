import { render, screen } from "@testing-library/react";

import { App } from "../src/App";

test("renders the scaffold root", () => {
  render(<App />);
  expect(screen.getByRole("main")).toBeInTheDocument();
});
