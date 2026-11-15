import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ClassBadge, Delta, RankChange, ScoreBar, Segmented } from "./ui";

describe("ClassBadge", () => {
  it("never relies on colour alone: a glyph and a text label are always present", () => {
    const { container, rerender } = render(<ClassBadge cls="ESTABLISHED_BULLISH" />);
    expect(screen.getByText("Established Bullish")).toBeInTheDocument();
    expect(container.textContent).toContain("▲");
    rerender(<ClassBadge cls="DEVELOPING_BEARISH" compact />);
    expect(screen.getByText("Dev. bear")).toBeInTheDocument();
    expect(container.textContent).toContain("▼");
    rerender(<ClassBadge cls="NEUTRAL" />);
    expect(container.textContent).toContain("●");
  });

  it("shows a dash when a stock has no class", () => {
    render(<ClassBadge cls={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("Delta and RankChange", () => {
  it("prints direction glyph, sign and value", () => {
    const { container, rerender } = render(<Delta value={2.5} />);
    expect(container.textContent).toBe("▲+2.50%");
    rerender(<Delta value={-1} digits={1} />);
    expect(container.textContent).toBe("▼−1.0%");
    rerender(<Delta value={null} />);
    expect(container.textContent).toBe("—");
  });

  it("marks stocks that were not ranked yesterday as new", () => {
    const { container, rerender } = render(<RankChange value={null} />);
    expect(container.textContent).toBe("new");
    rerender(<RankChange value={5} />);
    expect(container.textContent).toBe("▲+5");
  });
});

describe("ScoreBar", () => {
  it("clamps the bar width to 0-100%", () => {
    const { container } = render(<ScoreBar value={140} />);
    const fill = container.querySelector("[style]") as HTMLElement;
    expect(fill.style.width).toBe("100%");
    expect(screen.getByText("140.0")).toBeInTheDocument();
  });
});

describe("Segmented", () => {
  it("reports the chosen option and marks it checked", () => {
    const onChange = vi.fn();
    render(
      <Segmented
        value="prim"
        onChange={onChange}
        label="MST algorithm"
        options={[
          { value: "prim", label: "Prim" },
          { value: "kruskal", label: "Kruskal" },
        ]}
      />,
    );
    expect(screen.getByRole("radio", { name: "Prim" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: "Kruskal" }));
    expect(onChange).toHaveBeenCalledWith("kruskal");
  });
});
