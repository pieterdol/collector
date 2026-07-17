import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Lightbox } from "../components/Lightbox";

const images = ["/media/a.jpg", "/media/b.jpg", "/media/c.jpg"];

describe("Lightbox", () => {
  it("shows the requested image", () => {
    render(<Lightbox images={images} index={1} onClose={() => {}} onIndex={() => {}} />);
    expect(document.querySelector("img")).toHaveAttribute("src", "/media/b.jpg");
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
  });

  it("closes on backdrop click but not on image click", () => {
    const onClose = vi.fn();
    render(<Lightbox images={images} index={0} onClose={onClose} onIndex={() => {}} />);
    fireEvent.click(document.querySelector("img")!);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("navigates with arrows and wraps around", () => {
    const onIndex = vi.fn();
    render(<Lightbox images={images} index={2} onClose={() => {}} onIndex={onIndex} />);
    fireEvent.click(screen.getByLabelText("Next screenshot"));
    expect(onIndex).toHaveBeenCalledWith(0); // wraps
    fireEvent.click(screen.getByLabelText("Previous screenshot"));
    expect(onIndex).toHaveBeenCalledWith(1);
  });

  it("responds to Escape and arrow keys", () => {
    const onClose = vi.fn();
    const onIndex = vi.fn();
    render(<Lightbox images={images} index={0} onClose={onClose} onIndex={onIndex} />);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(onIndex).toHaveBeenCalledWith(1);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("hides navigation for a single image", () => {
    render(<Lightbox images={["/media/a.jpg"]} index={0} onClose={() => {}} onIndex={() => {}} />);
    expect(screen.queryByLabelText("Next screenshot")).not.toBeInTheDocument();
  });
});
