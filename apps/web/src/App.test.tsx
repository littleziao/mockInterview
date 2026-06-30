import { render, screen } from "@testing-library/react";

import { App } from "./App";

describe("App", () => {
  it("renders the local mock interview shell", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "AI 模拟面试工作台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "新建面试" })).toBeInTheDocument();
    expect(screen.getByText("FastAPI / SQLite 就绪")).toBeInTheDocument();
  });
});

